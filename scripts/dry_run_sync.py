"""Phase 2 script: fetch transactions and print what would be written to Odoo."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.clients.biotime_client import BioTimeClient
from app.clients.odoo_client import OdooClient
from app.services.attendance_service import AttendanceService
from app.services.employee_mapper import EmployeeMapper
from app.services.punch_normalizer import PunchNormalizer
from app.services.sync_service import SyncService
from app.logging_config import setup_logging
from app.utils.datetime_utils import local_now_string

setup_logging()


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else (settings.sync_start_from or "2026-05-01 00:00:00")
    end = sys.argv[2] if len(sys.argv) > 2 else local_now_string(settings.local_timezone)

    print(f"DRY RUN: {start} → {end}\n")

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

    sync_service = SyncService(
        biotime=biotime,
        employee_mapper=EmployeeMapper(odoo, settings.odoo_employee_code_field),
        attendance_service=AttendanceService(odoo),
        normalizer=PunchNormalizer(),
        local_timezone=settings.local_timezone,
        dry_run=True,
    )

    stats = sync_service.sync_range(start_time=start, end_time=end, page_size=settings.sync_page_size)
    print(f"\nStats: {stats}")


if __name__ == "__main__":
    main()
