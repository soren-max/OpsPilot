from app.workflows.change import build_change_graph


def test_change_graph_ends_at_durable_approval_wait() -> None:
    result = build_change_graph().invoke(
        {
            "change_id": "change-1",
            "incident_id": "incident-1",
            "workflow_id": "workflow-1",
            "status": "PROPOSED",
            "current_node": "",
        }
    )
    assert result["status"] == "WAITING_APPROVAL"
    assert result["current_node"] == "request_approval"


def test_change_graph_models_every_external_gate_and_final_verification() -> None:
    result = build_change_graph().invoke(
        {
            "change_id": "change-1",
            "incident_id": "incident-1",
            "workflow_id": "workflow-1",
            "status": "PROPOSED",
            "current_node": "",
            "approval_granted": True,
            "review_approved": True,
            "merged": True,
            "gitops_synced": True,
            "gitops_healthy": True,
            "verification_passed": True,
        }
    )
    assert result["status"] == "RESOLVED"
    assert result["current_node"] == "finalize"
