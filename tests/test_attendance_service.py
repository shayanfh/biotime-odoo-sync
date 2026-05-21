from unittest.mock import MagicMock
from app.services.attendance_service import AttendanceService


def make_service(search_result=None, create_return=10):
    odoo = MagicMock()
    odoo.search_read.return_value = search_result or []
    odoo.create.return_value = create_return
    odoo.write.return_value = True
    return AttendanceService(odoo=odoo)


def test_find_open_attendance_returns_record():
    record = {"id": 7, "employee_id": [1, "Ali"], "check_in": "2026-05-01 04:00:00", "check_out": False}
    svc = make_service(search_result=[record])
    result = svc.find_open_attendance(1)
    assert result["id"] == 7


def test_find_open_attendance_returns_none():
    svc = make_service(search_result=[])
    assert svc.find_open_attendance(1) is None


def test_create_check_in_returns_id():
    svc = make_service(create_return=42)
    attendance_id = svc.create_check_in(1, "2026-05-01 04:00:00")
    assert attendance_id == 42
    svc.odoo.create.assert_called_once()


def test_close_check_out():
    svc = make_service()
    result = svc.close_check_out(7, "2026-05-01 13:00:00")
    assert result is True
    svc.odoo.write.assert_called_once_with("hr.attendance", [7], {"check_out": "2026-05-01 13:00:00"})
