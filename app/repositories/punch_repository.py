import json
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.models import RawPunch


class PunchRepository:
    def __init__(self, session: Session):
        self.session = session

    def exists(self, biotime_id: int) -> bool:
        return self.session.query(RawPunch).filter_by(biotime_id=biotime_id).first() is not None

    def insert_pending(self, punch_data: dict) -> RawPunch | None:
        record = RawPunch(
            biotime_id=int(punch_data["id"]),
            emp_code=str(punch_data["emp_code"]),
            punch_time=str(punch_data["punch_time"]),
            punch_state=str(punch_data.get("punch_state", "")),
            terminal_sn=punch_data.get("terminal_sn"),
            raw_payload=json.dumps(punch_data),
            status="pending",
        )
        try:
            self.session.add(record)
            self.session.commit()
            return record
        except IntegrityError:
            self.session.rollback()
            return None  # already exists

    def mark_synced(self, biotime_id: int, odoo_employee_id: int, odoo_attendance_id: int | None) -> None:
        self.session.query(RawPunch).filter_by(biotime_id=biotime_id).update(
            {
                "status": "synced",
                "odoo_employee_id": odoo_employee_id,
                "odoo_attendance_id": odoo_attendance_id,
                "processed_at": datetime.utcnow(),
                "error_message": None,
            }
        )
        self.session.commit()

    def mark_failed(self, biotime_id: int, error: str) -> None:
        self.session.query(RawPunch).filter_by(biotime_id=biotime_id).update(
            {
                "status": "failed",
                "error_message": error[:1000],
                "processed_at": datetime.utcnow(),
            }
        )
        self.session.commit()

    def mark_skipped(self, biotime_id: int, reason: str) -> None:
        self.session.query(RawPunch).filter_by(biotime_id=biotime_id).update(
            {
                "status": "skipped",
                "error_message": reason,
                "processed_at": datetime.utcnow(),
            }
        )
        self.session.commit()
