import pytest
from app.services.punch_normalizer import PunchNormalizer, NormalizedPunch


def make_normalizer():
    return PunchNormalizer()


def test_normalize_basic():
    raw = {"id": 1, "emp_code": "1001", "punch_time": "2026-05-01 08:00:00", "punch_state": "0"}
    punch = make_normalizer().normalize(raw)
    assert punch.biotime_id == 1
    assert punch.emp_code == "1001"
    assert punch.is_check_in is True
    assert punch.is_check_out is False


def test_normalize_check_out():
    raw = {"id": 2, "emp_code": "1001", "punch_time": "2026-05-01 17:00:00", "punch_state": "1"}
    punch = make_normalizer().normalize(raw)
    assert punch.is_check_in is False
    assert punch.is_check_out is True


def test_normalize_missing_id():
    with pytest.raises(ValueError, match="id"):
        make_normalizer().normalize({"emp_code": "1001", "punch_time": "2026-05-01 08:00:00"})


def test_normalize_missing_emp_code():
    with pytest.raises(ValueError, match="emp_code"):
        make_normalizer().normalize({"id": 1, "punch_time": "2026-05-01 08:00:00"})


def test_normalize_optional_fields_default_to_none():
    raw = {"id": 3, "emp_code": "2002", "punch_time": "2026-05-01 09:00:00"}
    punch = make_normalizer().normalize(raw)
    assert punch.terminal_sn is None
    assert punch.terminal_alias is None
    assert punch.punch_state == ""
