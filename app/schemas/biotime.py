from pydantic import BaseModel


class BioTimeTransaction(BaseModel):
    id: int
    emp_code: str
    punch_time: str
    punch_state: str = ""
    terminal_sn: str | None = None
    terminal_alias: str | None = None
    upload_time: str | None = None
    is_attendance: str | None = None


class BioTimeEmployee(BaseModel):
    emp_code: str
    first_name: str = ""
    last_name: str = ""
    department: str | None = None


class BioTimePagedResponse(BaseModel):
    count: int
    next: str | None = None
    previous: str | None = None
    data: list[dict] = []
