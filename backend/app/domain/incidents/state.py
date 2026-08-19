from typing import TypedDict


class IncidentState(TypedDict):
    incident_id: str
    user_query: str
    evidence: list[str]
    hypotheses: list[str]
    decision_summary: str | None
