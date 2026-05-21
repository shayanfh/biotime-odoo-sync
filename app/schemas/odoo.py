from pydantic import BaseModel


class OdooEmployee(BaseModel):
    id: int
    name: str


class OdooAttendance(BaseModel):
    id: int
    employee_id: list  # Odoo returns [id, name]
    check_in: str
    check_out: str | bool = False
