import logging
from collections import defaultdict

from app.clients.biotime_client import BioTimeClient
from app.repositories.punch_repository import PunchRepository
from app.services.attendance_service import AttendanceService
from app.services.employee_mapper import EmployeeMapper
from app.services.punch_normalizer import PunchNormalizer
from app.utils.datetime_utils import local_to_utc_string

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(
        self,
        biotime: BioTimeClient,
        employee_mapper: EmployeeMapper,
        attendance_service: AttendanceService,
        normalizer: PunchNormalizer,
        local_timezone: str,
        dry_run: bool = False,
        punch_repo: PunchRepository | None = None,
        auto_checkout_time: str = "19:00",
    ):
        self.biotime = biotime
        self.employee_mapper = employee_mapper
        self.attendance_service = attendance_service
        self.normalizer = normalizer
        self.local_timezone = local_timezone
        self.dry_run = dry_run
        self.punch_repo = punch_repo
        self.auto_checkout_time = auto_checkout_time

    def sync_range(
        self,
        start_time: str,
        end_time: str,
        page_size: int = 1000,
        punch_repo: PunchRepository | None = None,
    ) -> dict:
        if punch_repo is not None:
            self.punch_repo = punch_repo

        stats = {
            "fetched": 0,
            "loaded": 0,
            "skipped_existing": 0,
            "processed_days": 0,
            "auto_checkout": 0,
            "errors": 0,
        }

        logger.info("Starting sync: %s → %s (dry_run=%s)", start_time, end_time, self.dry_run)

        # ── Phase 1: fetch all pages and save raw punches with status=loaded ──
        self._load_all_punches(start_time, end_time, page_size, stats)

        # ── Phase 2: group by (emp_code, date) and push to Odoo ──────────────
        self._process_loaded_punches(stats)

        logger.info("Sync complete: %s", stats)
        return stats

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 1
    # ─────────────────────────────────────────────────────────────────────────

    def _load_all_punches(self, start_time: str, end_time: str, page_size: int, stats: dict) -> None:
        page = 1
        logger.info("Phase 1 – fetching punches from BioTime: %s → %s", start_time, end_time)

        while True:
            response = self.biotime.get_transactions(
                start_time=start_time,
                end_time=end_time,
                page=page,
                page_size=page_size,
            )

            rows = response.get("data") or response.get("results") or []
            if not rows:
                break

            stats["fetched"] += len(rows)
            logger.info("Phase 1 – page %d: %d transactions", page, len(rows))

            for raw_punch in rows:
                biotime_id = raw_punch.get("id")

                if self.punch_repo and self.punch_repo.exists(biotime_id):
                    logger.debug("Punch biotime_id=%s already in DB, skipping", biotime_id)
                    stats["skipped_existing"] += 1
                    continue

                if self.punch_repo:
                    self.punch_repo.insert_loaded(raw_punch)

                stats["loaded"] += 1

            if not response.get("next"):
                break
            page += 1

        logger.info(
            "Phase 1 complete – fetched=%d  loaded=%d  skipped_existing=%d",
            stats["fetched"], stats["loaded"], stats["skipped_existing"],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 2
    # ─────────────────────────────────────────────────────────────────────────

    def _process_loaded_punches(self, stats: dict) -> None:
        if not self.punch_repo:
            return

        loaded = self.punch_repo.get_loaded_punches()
        if not loaded:
            logger.info("Phase 2 – no loaded punches to process")
            return

        logger.info("Phase 2 – processing %d loaded punches", len(loaded))

        # Group by (emp_code, date)
        groups: dict = defaultdict(list)
        for punch in loaded:
            date = str(punch.punch_time)[:10]  # "YYYY-MM-DD"
            groups[(str(punch.emp_code), date)].append(punch)

        logger.info("Phase 2 – %d employee-day groups found", len(groups))

        for (emp_code, date), punches in groups.items():
            punches.sort(key=lambda p: p.punch_time)
            biotime_ids = [p.biotime_id for p in punches]
            try:
                self._process_day_group(emp_code, date, punches, biotime_ids, stats)
            except Exception as exc:
                self.punch_repo.mark_group_failed(biotime_ids, str(exc))
                stats["errors"] += 1
                logger.error("emp_code=%s date=%s – failed: %s", emp_code, date, exc)

    def _process_day_group(
        self,
        emp_code: str,
        date: str,
        punches: list,
        biotime_ids: list[int],
        stats: dict,
    ) -> None:
        assert self.punch_repo is not None
        employee = self.employee_mapper.find_employee_by_biotime_code(emp_code)
        if not employee:
            raise ValueError(f"No Odoo employee for BioTime emp_code={emp_code}")

        employee_id = employee["id"]

        check_in_time = punches[0].punch_time
        check_in_utc = local_to_utc_string(check_in_time, self.local_timezone)

        if len(punches) > 1:
            check_out_time = punches[-1].punch_time
            check_out_utc = local_to_utc_string(check_out_time, self.local_timezone)
            auto_applied = False
            logger.info(
                "emp_code=%s date=%s – %d punches | check_in=%s  check_out=%s",
                emp_code, date, len(punches), check_in_time, check_out_time,
            )
        else:
            auto_checkout_local = f"{date} {self.auto_checkout_time}:00"
            check_out_utc = local_to_utc_string(auto_checkout_local, self.local_timezone)
            auto_applied = True
            logger.info(
                "emp_code=%s date=%s – single punch at %s | auto check_out applied at %s",
                emp_code, date, check_in_time, auto_checkout_local,
            )

        if self.dry_run:
            logger.info(
                "[DRY RUN] Would create attendance for employee_id=%d: check_in=%s  check_out=%s",
                employee_id, check_in_utc, check_out_utc,
            )
            self.punch_repo.mark_group_synced(biotime_ids, employee_id, None)
            stats["processed_days"] += 1
            if auto_applied:
                stats["auto_checkout"] += 1
            return

        attendance_id = self.attendance_service.create_full_attendance(
            employee_id, check_in_utc, check_out_utc
        )
        self.punch_repo.mark_group_synced(biotime_ids, employee_id, attendance_id)

        stats["processed_days"] += 1
        if auto_applied:
            stats["auto_checkout"] += 1
