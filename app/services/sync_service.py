import logging

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
    ):
        self.biotime = biotime
        self.employee_mapper = employee_mapper
        self.attendance_service = attendance_service
        self.normalizer = normalizer
        self.local_timezone = local_timezone
        self.dry_run = dry_run
        self.punch_repo = punch_repo

    def sync_range(self, start_time: str, end_time: str, page_size: int = 1000, punch_repo: PunchRepository | None = None) -> dict:
        stats = {"fetched": 0, "created_check_in": 0, "closed_check_out": 0, "skipped": 0, "errors": 0}
        page = 1

        logger.info("Starting sync: %s → %s (dry_run=%s)", start_time, end_time, self.dry_run)

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
            logger.info("Page %d: %d transactions", page, len(rows))

            for raw_punch in rows:
                biotime_id = raw_punch.get("id")

                # Skip punches already registered in the DB
                if self.punch_repo and self.punch_repo.exists(biotime_id):
                    logger.info("Punch biotime_id=%s already processed, skipping", biotime_id)
                    stats["skipped"] += 1
                    continue

                # Register as pending so we never reprocess it
                if self.punch_repo:
                    self.punch_repo.insert_pending(raw_punch)

                try:
                    result = self.process_raw_punch(raw_punch)
                    status = result.get("status", "unknown")
                    if status in stats:
                        stats[status] += 1
                    else:
                        stats["skipped"] += 1

                    if self.punch_repo:
                        if status == "created_check_in":
                            attendance_id = result.get("attendance_id")
                            self.punch_repo.mark_synced(biotime_id, result.get("employee_id"), attendance_id)
                        elif status == "closed_check_out":
                            attendance_id = result.get("attendance_id")
                            self.punch_repo.mark_synced(biotime_id, result.get("employee_id"), attendance_id)
                        elif status == "skipped":
                            reason = result.get("reason", "skipped")
                            self.punch_repo.mark_skipped(biotime_id, reason)

                except Exception as exc:
                    if self.punch_repo:
                        self.punch_repo.mark_failed(biotime_id, str(exc))
                    stats["errors"] += 1
                    logger.error("Failed to process punch %s: %s", biotime_id, exc)

            if not response.get("next"):
                break
            page += 1

        logger.info("Sync complete: %s", stats)
        return stats

    def process_raw_punch(self, raw_punch: dict) -> dict:
        punch = self.normalizer.normalize(raw_punch)

        employee = self.employee_mapper.find_employee_by_biotime_code(punch.emp_code)
        if not employee:
            raise ValueError(f"No Odoo employee for BioTime emp_code={punch.emp_code}")

        employee_id = employee["id"]
        punch_time_utc = local_to_utc_string(punch.punch_time, self.local_timezone)

        if punch.is_check_in:
            open_attendance = self.attendance_service.find_open_attendance(employee_id)
            if open_attendance:
                logger.warning(
                    "emp_code=%s already has open attendance id=%d, skipping check-in",
                    punch.emp_code,
                    open_attendance["id"],
                )
                return {"status": "skipped", "reason": "already_open", "employee_id": employee_id}

            if self.dry_run:
                logger.info("[DRY RUN] Would create check_in for employee_id=%d at %s", employee_id, punch_time_utc)
                return {"status": "created_check_in", "employee_id": employee_id, "attendance_id": None}

            attendance_id = self.attendance_service.create_check_in(employee_id, punch_time_utc)
            return {"status": "created_check_in", "employee_id": employee_id, "attendance_id": attendance_id}

        if punch.is_check_out:
            open_attendance = self.attendance_service.find_open_attendance(employee_id)
            if not open_attendance:
                raise ValueError(f"Check-out received but no open attendance for emp_code={punch.emp_code}")

            if self.dry_run:
                logger.info(
                    "[DRY RUN] Would close attendance id=%d for employee_id=%d at %s",
                    open_attendance["id"],
                    employee_id,
                    punch_time_utc,
                )
                return {"status": "closed_check_out", "employee_id": employee_id, "attendance_id": open_attendance["id"]}

            self.attendance_service.close_check_out(open_attendance["id"], punch_time_utc)
            return {"status": "closed_check_out", "employee_id": employee_id, "attendance_id": open_attendance["id"]}

        raise ValueError(f"Unknown punch_state={punch.punch_state!r} for emp_code={punch.emp_code}")
