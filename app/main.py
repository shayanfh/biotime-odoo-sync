import logging
import sys
import calendar
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

from app.config import settings
from app.logging_config import setup_logging
from app.clients.biotime_client import BioTimeClient
from app.clients.odoo_client import OdooClient
from app.db.database import init_db
from app.repositories.punch_repository import PunchRepository
from app.repositories.sync_state_repository import SyncStateRepository
from app.services.attendance_service import AttendanceService
from app.services.employee_mapper import EmployeeMapper
from app.services.punch_normalizer import PunchNormalizer
from app.services.sync_service import SyncService

logger = logging.getLogger(__name__)

INITIAL_SYNC_DONE_KEY = "initial_3_month_sync_done"
INITIAL_SYNC_DONE_VALUE = "true"
LAST_DAILY_SYNC_DATE_KEY = "last_daily_sync_date"


def subtract_months(dt: datetime, months: int) -> datetime:
    """
    Subtract calendar months without adding extra dependencies.
    Example: 2026-05-25 - 3 months = 2026-02-25
    """
    month = dt.month - months
    year = dt.year

    while month <= 0:
        month += 12
        year -= 1

    last_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, last_day)

    return dt.replace(year=year, month=month, day=day)


def format_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def get_local_now() -> datetime:
    return datetime.now(ZoneInfo(settings.local_timezone))


def get_initial_sync_window() -> tuple[str, str]:
    end_dt = get_local_now() - timedelta(days=1)
    end_dt = end_dt.replace(hour=23, minute=59, second=59)
    start_dt = subtract_months(end_dt, settings.initial_sync_months)

    return format_dt(start_dt), format_dt(end_dt)


def get_today_sync_window() -> tuple[str, str, str]:
    now_dt = get_local_now()

    start_dt = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = now_dt.replace(microsecond=0)

    sync_date = now_dt.strftime("%Y-%m-%d")

    return format_dt(start_dt), format_dt(end_dt), sync_date


def build_sync_service(dry_run: bool = False) -> SyncService:
    biotime = BioTimeClient(
        base_url=settings.biotime_base_url,
        username=settings.biotime_username,
        password=settings.biotime_password,
        auth_type=settings.biotime_auth_type,
    )

    odoo = OdooClient(
        url=settings.odoo_url,
        db=settings.odoo_db,
        username=settings.odoo_username,
        password=settings.odoo_password,
    )

    employee_mapper = EmployeeMapper(
        odoo=odoo,
        employee_code_field=settings.odoo_employee_code_field,
    )

    attendance_service = AttendanceService(odoo)
    normalizer = PunchNormalizer()

    return SyncService(
        biotime=biotime,
        employee_mapper=employee_mapper,
        attendance_service=attendance_service,
        normalizer=normalizer,
        local_timezone=settings.local_timezone,
        dry_run=dry_run,
        auto_checkout_time=settings.auto_checkout_time,
    )


def run_sync_range(
    start_time: str,
    end_time: str,
    dry_run: bool = False,
) -> dict:
    SessionLocal = init_db(settings.database_url)
    sync_service = build_sync_service(dry_run=dry_run)

    with SessionLocal() as session:
        punch_repo = PunchRepository(session)

        logger.info("Sync window: %s → %s", start_time, end_time)

        stats = sync_service.sync_range(
            start_time=start_time,
            end_time=end_time,
            page_size=settings.sync_page_size,
            punch_repo=punch_repo,
        )

        logger.info("Sync finished. Stats: %s", stats)

        error_count = stats.get("errors", 0)
        if error_count > 0:
            logger.warning(
                "⚠  Done. You have %d failed punch group(s) that could not be saved to Odoo. "
                "Please check the logs above, fix the issue, and run again — failed punches will be retried automatically.",
                error_count,
            )

        return stats


def clear_today_punches() -> None:
    today = get_local_now().strftime("%Y-%m-%d")
    SessionLocal = init_db(settings.database_url)

    with SessionLocal() as session:
        punch_repo = PunchRepository(session)
        deleted = punch_repo.delete_by_date(today)

    logger.info("Cleared %d punch record(s) for today (%s) from local DB.", deleted, today)


def run_initial_sync_if_needed(dry_run: bool = False) -> None:
    SessionLocal = init_db(settings.database_url)

    with SessionLocal() as session:
        state_repo = SyncStateRepository(session)

        initial_done = state_repo.get(INITIAL_SYNC_DONE_KEY)

        if initial_done == INITIAL_SYNC_DONE_VALUE:
            logger.info("Initial 3-month sync already done. Skipping.")
            return

    start_time, end_time = get_initial_sync_window()

    logger.info(
        "Initial 3-month sync not done yet. Running initial sync: %s → %s",
        start_time,
        end_time,
    )

    stats = run_sync_range(
        start_time=start_time,
        end_time=end_time,
        dry_run=dry_run,
    )

    if dry_run:
        logger.info("[DRY RUN] Initial sync state will not be saved.")
        return

    if stats.get("errors", 0) > 0:
        logger.error(
            "Initial sync finished with errors. State will not be marked as done. Stats: %s",
            stats,
        )
        return

    with SessionLocal() as session:
        state_repo = SyncStateRepository(session)
        state_repo.set(INITIAL_SYNC_DONE_KEY, INITIAL_SYNC_DONE_VALUE)
        state_repo.set("initial_3_month_sync_start_time", start_time)
        state_repo.set("initial_3_month_sync_end_time", end_time)

    logger.info("Initial 3-month sync marked as done.")


def run_daily_sync(dry_run: bool = False) -> None:
    try:
        _run_daily_sync(dry_run=dry_run)
    except Exception:
        logger.exception("Unhandled exception in daily sync job")


def _run_daily_sync(dry_run: bool = False) -> None:
    start_time, end_time, sync_date = get_today_sync_window()

    logger.info(
        "Running daily sync for date=%s window=%s → %s",
        sync_date,
        start_time,
        end_time,
    )

    stats = run_sync_range(
        start_time=start_time,
        end_time=end_time,
        dry_run=dry_run,
    )

    if dry_run:
        logger.info("[DRY RUN] Daily sync date will not be saved.")
        return

    if stats.get("errors", 0) > 0:
        logger.error(
            "Daily sync finished with errors. Last daily sync date will not be updated. Stats: %s",
            stats,
        )
        return

    SessionLocal = init_db(settings.database_url)

    with SessionLocal() as session:
        state_repo = SyncStateRepository(session)
        state_repo.set(LAST_DAILY_SYNC_DATE_KEY, sync_date)

    logger.info("Daily sync completed for date=%s", sync_date)


def start_scheduler(dry_run: bool = False) -> None:
    scheduler = BlockingScheduler(timezone=settings.local_timezone)

    scheduler.add_job(
        run_daily_sync,
        trigger="cron",
        hour=settings.daily_sync_hour,
        minute=settings.daily_sync_minute,
        kwargs={"dry_run": dry_run},
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
        id="daily_biotime_odoo_sync",
        replace_existing=True,
    )

    logger.info(
        "Scheduler started. Daily sync will run every day at %02d:%02d timezone=%s",
        settings.daily_sync_hour,
        settings.daily_sync_minute,
        settings.local_timezone,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping scheduler...")
        scheduler.shutdown()


def main(dry_run: bool = False) -> None:
    setup_logging(level=settings.log_level)

    clear_today_punches()

    run_initial_sync_if_needed(dry_run=dry_run)

    # start_scheduler(dry_run=dry_run)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    once = "--once" in sys.argv

    if once:
        setup_logging(level=settings.log_level)
        run_daily_sync(dry_run=dry)
    else:
        main(dry_run=dry)