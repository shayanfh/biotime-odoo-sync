"""Test script: load punch data from data/employee_example_result.json
and run it through SyncService to create / update hr.attendance in Odoo.

Path : scripts/test_sync_from_json.py
Run  : python scripts/test_sync_from_json.py [--dry-run]
"""

import json
import sys
import os
import argparse
import logging
from typing import Any

# ---------------------------------------------------------------------------
# Make sure the project root is on sys.path
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

# Repo-level imports
from app.config import settings  # noqa: E402
from app.db.database import init_db  # noqa: E402
from app.repositories.punch_repository import PunchRepository  # noqa: E402
from app.repositories.sync_state_repository import SyncStateRepository  # noqa: E402
from app.services.attendance_service import AttendanceService  # noqa: E402
from app.services.employee_mapper import EmployeeMapper  # noqa: E402
from app.services.punch_normalizer import PunchNormalizer  # noqa: E402
from app.services.sync_service import SyncService  # noqa: E402
from app.clients.biotime_client import BioTimeClient  # noqa: E402
from app.logging_config import setup_logging  # noqa: E402


# ---------------------------------------------------------------------------
# Minimal BioTime stub – replaces HTTP calls with local file data
# ---------------------------------------------------------------------------
class MockBioTimeClient:
    """Drop-in replacement for BioTimeClient that feeds data from a JSON file."""

    def __init__(self, json_path: str) -> None:
        self._payload = self._load(json_path)
        logger = logging.getLogger(self.__class__.__name__)
        logger.info("Loaded %d punches from %s", len(self._payload), json_path)

    @staticmethod
    def _load(path: str) -> list[dict[str, Any]]:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def get_transactions(
        self,
        start_time: str,
        end_time: str,
        page: int = 1,
        page_size: int = 1000,
        emp_code: str | None = None,
        terminal_sn: str | None = None,
    ) -> dict[str, Any]:
        # Ignore paging params – return everything in one shot like page 1
        return {"data": list(self._payload), "next": None}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test sync from local JSON → Odoo")
    parser.add_argument("--json", default=os.path.join(PROJECT_ROOT, "data", "employee_example_result.json"),
                        help="Path to the JSON punch file")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what *would* happen without touching Odoo")
    return parser.parse_args()


def main() -> None:
    setup_logging(level=settings.log_level)
    args = parse_args()

    db_path = os.path.join(PROJECT_ROOT, "sync.db")
    logger = logging.getLogger("test_sync_from_json")

    # ------------------------------------------------------------------ DB
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    database_url = f"sqlite:///{db_path}"
    SessionLocal = init_db(database_url)
    logger.info("Using local SQLite DB at %s", db_path)

    # ------------------------------------------------------------------ Clients
    biotime = MockBioTimeClient(args.json)

    from app.clients.odoo_client import OdooClient  # local import to keep clarity
    odoo = OdooClient(
        url=settings.odoo_url,
        db=settings.odoo_db,
        username=settings.odoo_username,
        password=settings.odoo_password,
    )

    # ------------------------------------------------------------------ Mappers / services
    employee_mapper = EmployeeMapper(odoo=odoo, employee_code_field=settings.odoo_employee_code_field)
    attendance_service = AttendanceService(odoo)
    normalizer = PunchNormalizer()

    sync_service = SyncService(
        biotime=biotime,
        employee_mapper=employee_mapper,
        attendance_service=attendance_service,
        normalizer=normalizer,
        local_timezone=settings.local_timezone,
        dry_run=args.dry_run,
    )

    # ------------------------------------------------------------------ Run
    with SessionLocal() as session:
        state_repo = SyncStateRepository(session)
        punch_repo = PunchRepository(session)

        stats = sync_service.sync_range(
            start_time="2025-01-01 00:00:00",
            end_time="2099-01-01 00:00:00",
            page_size=1000,
            punch_repo=punch_repo,
        )

    print("\n─── Sync finished ───")
    for k, v in stats.items():
        print(f"  {k:25s}: {v}")


if __name__ == "__main__":
    main()
