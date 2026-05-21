from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class RawPunch(Base):
    __tablename__ = "raw_punches"

    id = Column(Integer, primary_key=True)
    biotime_id = Column(Integer, nullable=False)
    emp_code = Column(String(100), nullable=False)
    punch_time = Column(String(50), nullable=False)
    punch_state = Column(String(20), nullable=True)
    terminal_sn = Column(String(100), nullable=True)

    raw_payload = Column(Text, nullable=False)

    # pending | synced | skipped | failed
    status = Column(String(30), default="pending", nullable=False)
    error_message = Column(Text, nullable=True)

    odoo_employee_id = Column(Integer, nullable=True)
    odoo_attendance_id = Column(Integer, nullable=True)

    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("biotime_id", name="uq_raw_punch_biotime_id"),)


class SyncState(Base):
    __tablename__ = "sync_state"

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(String(255), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
