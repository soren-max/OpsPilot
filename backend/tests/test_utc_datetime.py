from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Environment


def test_sqlite_restores_utc_timezone(db: Session) -> None:
    environment = db.scalar(select(Environment).limit(1))
    assert environment is not None
    assert environment.created_at.tzinfo is UTC
    assert environment.updated_at.tzinfo is UTC
