import logging
from app.clients.odoo_client import OdooClient

logger = logging.getLogger(__name__)


class AttendanceService:
    def __init__(self, odoo: OdooClient):
        self.odoo = odoo

    def find_open_attendance(self, employee_id: int) -> dict | None:
        records = self.odoo.search_read(
            "hr.attendance",
            [["employee_id", "=", employee_id], ["check_out", "=", False]],
            ["id", "employee_id", "check_in", "check_out"],
            limit=1,
            order="check_in desc",
        )
        return records[0] if records else None

    def create_check_in(self, employee_id: int, check_in_utc: str) -> int:
        attendance_id = self.odoo.create(
            "hr.attendance",
            {"employee_id": employee_id, "check_in": check_in_utc},
        )
        logger.debug("Created hr.attendance id=%d for employee_id=%d", attendance_id, employee_id)
        return attendance_id

    def create_full_attendance(self, employee_id: int, check_in_utc: str, check_out_utc: str) -> int:
        attendance_id = self.odoo.create(
            "hr.attendance",
            {"employee_id": employee_id, "check_in": check_in_utc, "check_out": check_out_utc},
        )
        logger.debug(
            "Created hr.attendance id=%d for employee_id=%d (check_in=%s, check_out=%s)",
            attendance_id, employee_id, check_in_utc, check_out_utc,
        )
        return attendance_id

    def close_check_out(self, attendance_id: int, check_out_utc: str) -> bool:
        result = self.odoo.write(
            "hr.attendance",
            [attendance_id],
            {"check_out": check_out_utc},
        )
        logger.debug("Closed hr.attendance id=%d with check_out=%s", attendance_id, check_out_utc)
        return result
