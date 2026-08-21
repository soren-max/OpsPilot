import json
import uuid
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
    knowledge_schema_version: str = "1"

    @property
    def knowledge_id(self) -> str:
        return str(
            uuid.uuid5(
                uuid.UUID("44677cd8-6b2c-4c45-9311-f933629f08e3"),
                f"{self.incident_id}:{self.knowledge_schema_version}",
            )
        )

    def serialize(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    def retrieval_text(self) -> str:
        fields = (
            ("title", (self.title,)),
            ("service", (self.service,)),
            ("environment", (self.environment,)),
            ("symptoms", self.symptoms),
            ("evidence_summary", self.evidence_summary),
            ("root_cause", (self.root_cause,)),
            ("contributing_factors", self.contributing_factors),
            ("remediation", self.remediation),
            ("verification", self.verification),
            ("tags", self.tags),
        )
        return "\n".join(f"{name}: {' | '.join(values)}" for name, values in fields if values)
