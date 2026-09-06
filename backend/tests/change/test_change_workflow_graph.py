from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.orm import Session

from app.change.service import ChangeService
from app.workflows.change import build_change_graph

from .conftest import intent, profile, seed_incident


def test_graph_reloads_durable_approval_across_controller_restart(db: Session) -> None:
    seed_incident(db)
    record = ChangeService(db, git=None).propose(intent(), profile())
    checkpoint = InMemorySaver()

    def advance(change_id: str) -> str:
        return ChangeService(db, git=None)._require(change_id).status.value

    config = {"configurable": {"thread_id": record.id}}
    graph = build_change_graph(advance=advance, checkpointer=checkpoint)
    assert graph.invoke({"change_id": record.id}, config)["status"] == "WAITING_APPROVAL"
    # Caller-supplied flags/status are not authority. Rebuilt controller reads SQL.
    restarted = build_change_graph(advance=advance, checkpointer=checkpoint)
    result = restarted.invoke(
        {"change_id": record.id, "status": "RESOLVED", "approval_granted": True}, config
    )
    assert result["status"] == "WAITING_APPROVAL"
    ChangeService(db, git=None).reject(record.id, actor="reviewer", reason="Reject change")
    assert restarted.invoke({"change_id": record.id}, config)["status"] == "REJECTED"
