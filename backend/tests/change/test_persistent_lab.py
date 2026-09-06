from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.change.lab import load_git, operate
from app.domain.change import ChangeStatus
from app.repositories.change_models import ChangeRecord


@pytest.mark.asyncio
async def test_external_review_survives_restart_and_status_is_read_only(tmp_path: Path) -> None:
    await operate(tmp_path, "up")
    engine = create_engine(f"sqlite:///{tmp_path / 'state.db'}")
    with Session(engine) as db:
        record = db.scalar(select(ChangeRecord))
        assert record is not None
        change_id = record.id
    engine.dispose()
    await operate(tmp_path, "approve", change_id)
    with pytest.raises(ValueError, match="External review"):
        await operate(tmp_path, "merge", change_id)
    await operate(tmp_path, "review", change_id)
    await operate(tmp_path, "status")
    git = load_git(tmp_path)
    assert len(git.pull_requests) == 1
    assert next(iter(git.pull_requests.values())).merged_revision is None
    await operate(tmp_path, "reconcile", change_id)
    await operate(tmp_path, "merge", change_id)
    await operate(tmp_path, "reconcile", change_id)
    engine = create_engine(f"sqlite:///{tmp_path / 'state.db'}")
    with Session(engine) as db:
        record = db.get(ChangeRecord, change_id)
        assert record is not None
        assert record.status is ChangeStatus.RESOLVED
    engine.dispose()
    assert len(load_git(tmp_path).pull_requests) == 1
