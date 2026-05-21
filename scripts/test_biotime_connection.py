"""Phase 1 script: verify BioTime connectivity and sample data."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.clients.biotime_client import BioTimeClient
from app.logging_config import setup_logging

setup_logging()


def main():
    client = BioTimeClient(
        base_url=settings.biotime_base_url,
        username=settings.biotime_username,
        password=settings.biotime_password,
        auth_type=settings.biotime_auth_type,
    )

    token = client.authenticate()
    print(f"\n✓ Auth OK  (token prefix: {token[:20]}...)\n")

    devices = client.get_devices(page=1, page_size=5)
    print("=== Devices ===")
    print(devices)

    employees = client.get_employees(page=1, page_size=5)
    print("\n=== Employees (first 5) ===")
    print(employees)

    start = settings.sync_start_from or "2026-05-01 00:00:00"
    transactions = client.get_transactions(
        start_time=start,
        end_time="2026-05-31 23:59:59",
        page=1,
        page_size=100,
    )
    print("\n=== Transactions (first 5) ===")
    print(transactions)


if __name__ == "__main__":
    main()
