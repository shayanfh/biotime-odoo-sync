"""Phase 1 script: verify Odoo connectivity and hr.employee/hr.attendance fields."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.clients.odoo_client import OdooClient
from app.logging_config import setup_logging

setup_logging()


def main():
    odoo = OdooClient(
        url=settings.odoo_url,
        db=settings.odoo_db,
        username=settings.odoo_username,
        password=settings.odoo_password,
    )

    print("\n✓ Odoo auth OK\n")

    employees = odoo.search_read(
        "hr.employee",
        [],
        ["id", "name", settings.odoo_employee_code_field],
        limit=5,
    )
    print(f"=== hr.employee (field={settings.odoo_employee_code_field}) ===")
    for emp in employees:
        print(emp)

    fields = odoo.fields_get("hr.attendance")
    print("\n=== hr.attendance field names ===")
    print(list(fields.keys()))


if __name__ == "__main__":
    main()
