from datetime import datetime
from sqlalchemy.orm import Session

from app.db.models import SyncState


class SyncStateRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, key: str) -> str | None:
        record = self.session.query(SyncState).filter_by(key=key).first()
        return record.value if record else None

    def set(self, key: str, value: str) -> None:
        record = self.session.query(SyncState).filter_by(key=key).first()
        if record:
            record.value = value
            record.updated_at = datetime.utcnow()
        else:
            record = SyncState(key=key, value=value, updated_at=datetime.utcnow())
            self.session.add(record)
        self.session.commit()
