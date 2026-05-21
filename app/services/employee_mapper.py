import logging
from app.clients.odoo_client import OdooClient

logger = logging.getLogger(__name__)


class EmployeeMapper:
    def __init__(self, odoo: OdooClient, employee_code_field: str = "barcode"):
        self.odoo = odoo
        self.employee_code_field = employee_code_field
        self._cache: dict[str, dict | None] = {}

    def find_employee_by_biotime_code(self, emp_code: str) -> dict | None:
        if emp_code in self._cache:
            return self._cache[emp_code]

        employees = self.odoo.search_read(
            "hr.employee",
            [[self.employee_code_field, "=", emp_code]],
            ["id", "name", self.employee_code_field],
            limit=1,
        )

        result = employees[0] if employees else None

        if result is None:
            logger.warning("No Odoo employee found for emp_code=%s", emp_code)

        self._cache[emp_code] = result
        return result
