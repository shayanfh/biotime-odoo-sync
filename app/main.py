import logging
import sys
from datetime import datetime, timedelta

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
from app.utils.datetime_utils import local_now_string

logger = logging.getLogger(__name__)

_LAST_SYNC_KEY = "last_sync_end_time"


def build_sync_window(state_repo: SyncStateRepository) -> tuple[str, str]:
    end_time = local_now_string(settings.local_timezone)

    last_sync = state_repo.get(_LAST_SYNC_KEY)
    if last_sync:
        start_time = last_sync
    elif settings.sync_start_from:
        start_time = settings.sync_start_from
    else:
        # default: last 24 hours
        start_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S") - timedelta(hours=24)
        start_time = start_dt.strftime("%Y-%m-%d %H:%M:%S")

    return start_time, end_time


def main(dry_run: bool = False) -> None:
    setup_logging()

    SessionLocal = init_db(settings.database_url)

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

    employee_mapper = EmployeeMapper(odoo=odoo, employee_code_field=settings.odoo_employee_code_field)
    attendance_service = AttendanceService(odoo)
    normalizer = PunchNormalizer()

    sync_service = SyncService(
        biotime=biotime,
        employee_mapper=employee_mapper,
        attendance_service=attendance_service,
        normalizer=normalizer,
        local_timezone=settings.local_timezone,
        dry_run=dry_run,
        auto_checkout_time=settings.auto_checkout_time,
    )

    with SessionLocal() as session:
        state_repo = SyncStateRepository(session)
        punch_repo = PunchRepository(session)
        start_time, end_time = build_sync_window(state_repo)

        logger.info("Sync window: %s → %s", start_time, end_time)
        stats = sync_service.sync_range(
            start_time=start_time,
            end_time=end_time,
            page_size=settings.sync_page_size,
            punch_repo=punch_repo,
        )

        if not dry_run and stats.get("errors", 0) == 0:
            state_repo.set(_LAST_SYNC_KEY, end_time)
            logger.info("Saved last_sync_end_time=%s", end_time)

    logger.info("Done. Stats: %s", stats)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
