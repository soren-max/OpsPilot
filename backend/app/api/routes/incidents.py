from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import response
from app.api.routes.auth import get_current_user
from app.application.incident_service import IncidentService
from app.core.config import get_settings
from app.db.session import get_db
from app.domain.incidents.models import IncidentStatus, Severity
from app.memory.factory import build_memory_store
from app.memory.service import KnowledgeQueryBuilder
from app.models import User
from app.repositories.incident_models import (
    DiagnosisRecord,
    EvidenceRecord,
    HypothesisRecord,
    IncidentRecord,
)
from app.repositories.incidents import IncidentRepository
from app.schemas_incidents import (
    DiagnosisCreate,
    DiagnosisRead,
    EvidenceCreate,
    EvidenceRead,
    HypothesisCreate,
    HypothesisRead,
    IncidentActionRead,
    IncidentCreate,
    IncidentPage,
    IncidentRead,
    RetrievedKnowledgeRead,
    VersionedMutation,
)
from app.services.rbac import require_permission

router = APIRouter(prefix="/incidents", tags=["incidents"])


def evidence_read(item: EvidenceRecord) -> EvidenceRead:
    return EvidenceRead(
        id=item.id,
        incident_id=item.incident_id,
        evidence_type=item.evidence_type,
        source=item.source,
        source_reference=item.source_reference,
        summary=item.summary,
        excerpt=item.excerpt,
        observed_at=item.observed_at,
        collected_at=item.collected_at,
        collector=item.collector,
        metadata=item.evidence_metadata,
        fingerprint=item.fingerprint,
    )


def hypothesis_read(item: HypothesisRecord) -> HypothesisRead:
    return HypothesisRead(
        id=item.id,
        incident_id=item.incident_id,
        statement=item.statement,
        confidence=item.confidence,
        status=item.status,
        supporting_evidence_ids=item.supporting_evidence_ids,
        contradicting_evidence_ids=item.contradicting_evidence_ids,
        created_at=item.created_at,
        created_by=item.created_by,
    )


def diagnosis_read(item: DiagnosisRecord) -> DiagnosisRead:
    return DiagnosisRead(
        id=item.id,
        incident_id=item.incident_id,
        root_cause=item.root_cause,
        contributing_factors=item.contributing_factors,
        evidence_ids=item.evidence_ids,
        confidence=item.confidence,
        created_by=item.created_by,
        created_at=item.created_at,
    )


def incident_read(item: IncidentRecord) -> IncidentRead:
    return IncidentRead(
        id=item.id,
        title=item.title,
        summary=item.summary,
        severity=item.severity,
        status=item.status,
        environment=item.environment,
        service=item.service,
        source=item.source,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
        resolved_at=item.resolved_at,
        closed_at=item.closed_at,
        tags=item.tags,
        version=item.version,
        evidence=[evidence_read(value) for value in item.evidence],
        hypotheses=[hypothesis_read(value) for value in item.hypotheses],
        diagnoses=[diagnosis_read(value) for value in item.diagnoses],
        actions=[
            IncidentActionRead(
                task_id=value.task_id,
                action_fingerprint=value.action_fingerprint,
                created_at=value.created_at,
            )
            for value in item.actions
        ],
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_incident(
    body: IncidentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.write")
    item = IncidentService(db).create_incident(body, user.username, request.state.request_id)
    return response(request, incident_read(item))


@router.get("")
def list_incidents(
    request: Request,
    incident_status: IncidentStatus | None = Query(default=None, alias="status"),
    severity: Severity | None = Query(default=None),
    service: str | None = Query(default=None, max_length=120),
    environment: str | None = Query(default=None, max_length=80),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    tags: list[str] = Query(default=[]),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.read")
    items, total = IncidentRepository(db).list(
        status=incident_status,
        severity=severity,
        service=service,
        environment=environment,
        created_from=created_from,
        created_to=created_to,
        tags=tuple(tags),
        offset=offset,
        limit=limit,
    )
    page = IncidentPage(
        items=[incident_read(item) for item in items],
        offset=offset,
        limit=limit,
        count=total,
    )
    return response(request, page)


@router.get("/{incident_id}")
def get_incident(
    incident_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.read")
    item = IncidentService(db)._require(incident_id)
    return response(request, incident_read(item))


@router.post("/{incident_id}/evidence", status_code=status.HTTP_201_CREATED)
def add_evidence(
    incident_id: str,
    body: EvidenceCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.write")
    item = IncidentService(db).add_evidence(
        incident_id, body, user.username, request.state.request_id
    )
    return response(request, evidence_read(item))


@router.post("/{incident_id}/hypotheses", status_code=status.HTTP_201_CREATED)
def add_hypothesis(
    incident_id: str,
    body: HypothesisCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.write")
    item = IncidentService(db).add_hypothesis(
        incident_id, body, user.username, request.state.request_id
    )
    return response(request, hypothesis_read(item))


@router.post("/{incident_id}/diagnosis", status_code=status.HTTP_201_CREATED)
def record_diagnosis(
    incident_id: str,
    body: DiagnosisCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.write")
    item = IncidentService(db).record_diagnosis(
        incident_id, body, user.username, request.state.request_id
    )
    return response(request, diagnosis_read(item))


@router.post("/{incident_id}/resolve")
def resolve_incident(
    incident_id: str,
    body: VersionedMutation,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.resolve")
    item = IncidentService(db).resolve(
        incident_id, body.expected_version, user.username, request.state.request_id
    )
    return response(request, incident_read(item))


@router.post("/{incident_id}/close")
def close_incident(
    incident_id: str,
    body: VersionedMutation,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.close")
    item = IncidentService(db).close(
        incident_id, body.expected_version, user.username, request.state.request_id
    )
    return response(request, incident_read(item))


@router.get("/{incident_id}/timeline")
def incident_timeline(
    incident_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.read")
    return response(request, IncidentService(db).timeline(incident_id))


@router.get("/{incident_id}/knowledge-record")
def incident_knowledge_record(
    incident_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.knowledge.read")
    return response(request, IncidentService(db).build_knowledge_record(incident_id))


@router.get("/{incident_id}/related")
def related_incidents(
    incident_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    require_permission(db, user, "incident.read")
    incident = IncidentService(db)._require(incident_id)
    settings = get_settings()
    retriever = build_memory_store(settings)
    if retriever is None:
        return response(request, [])
    query = KnowledgeQueryBuilder(settings.memory_retrieval_limit).build(
        service=incident.service,
        environment=incident.environment,
        symptoms=(incident.summary,),
        evidence_summary=tuple(item.summary for item in incident.evidence),
        severity=incident.severity.value,
        tags=tuple(incident.tags),
    )
    items = [
        RetrievedKnowledgeRead.model_validate(item, from_attributes=True)
        for item in retriever.retrieve(query)
        if item.incident_id != incident.id
    ]
    return response(request, items)
