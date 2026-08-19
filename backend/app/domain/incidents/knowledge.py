import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IncidentKnowledgeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    incident_id: str
    title: str
    service: str
    environment: str
    severity: str
    symptoms: tuple[str, ...]
    evidence_summary: tuple[str, ...]
    root_cause: str
    contributing_factors: tuple[str, ...]
    remediation: tuple[str, ...]
    verification: tuple[str, ...]
    tags: tuple[str, ...]
    resolved_at: datetime

    def serialize(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
