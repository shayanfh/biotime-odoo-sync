from unittest.mock import MagicMock
from app.services.employee_mapper import EmployeeMapper


def make_mapper(search_result):
    odoo = MagicMock()
    odoo.search_read.return_value = search_result
    return EmployeeMapper(odoo=odoo, employee_code_field="barcode")


def test_find_employee_found():
    mapper = make_mapper([{"id": 5, "name": "Ali Ahmad", "barcode": "1001"}])
    result = mapper.find_employee_by_biotime_code("1001")
    assert result is not None
    assert result["id"] == 5


def test_find_employee_not_found():
    mapper = make_mapper([])
    result = mapper.find_employee_by_biotime_code("9999")
    assert result is None


def test_find_employee_uses_cache():
    mapper = make_mapper([{"id": 5, "name": "Ali Ahmad", "barcode": "1001"}])
    mapper.find_employee_by_biotime_code("1001")
    mapper.find_employee_by_biotime_code("1001")
    assert mapper.odoo.search_read.call_count == 1
