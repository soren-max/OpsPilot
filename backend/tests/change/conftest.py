from __future__ import annotations

from app.db.base import utc_now
from app.domain.change import (
    ChangeIntent,
    ChangeType,
    GitOpsApplicationProfile,
    ManifestStrategy,
)
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.models import IncidentStatus, Severity
from app.repositories.incident_models import EvidenceRecord, IncidentRecord

BAD_IMAGE = "registry.example/demo-api@sha256:" + "b" * 64
GOOD_IMAGE = "registry.example/demo-api@sha256:" + "a" * 64
MANIFEST = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: demo-api
  template:
    metadata:
      labels:
        app: demo-api
    spec:
      containers:
        - name: demo-api
          image: {BAD_IMAGE}
"""


def seed_incident(db: object) -> tuple[IncidentRecord, EvidenceRecord]:
    now = utc_now()
    incident = IncidentRecord(
        id="incident-gitops-1",
        title="demo-api regression",
        summary="Error rate increased after deployment",
        severity=Severity.HIGH,
        status=IncidentStatus.MITIGATING,
        environment="production",
        service="demo-api",
        source="test",
        created_by="operator",
        tags=["gitops"],
        version=1,
        created_at=now,
        updated_at=now,
    )
    evidence = EvidenceRecord(
        id="evidence-current-1",
        incident=incident,
        evidence_type=EvidenceType.METRIC,
        source="prometheus",
        source_reference="metric-template:error-rate",
        summary="Current error rate is above threshold",
        observed_at=now,
        collected_at=now,
        collector="test",
        evidence_metadata={},
        fingerprint="e" * 64,
    )
    db.add_all([incident, evidence])  # type: ignore[attr-defined]
    db.commit()  # type: ignore[attr-defined]
    return incident, evidence


def profile() -> GitOpsApplicationProfile:
    return GitOpsApplicationProfile(
        profile_id="demo-api-production",
        service="demo-api",
        environment="production",
        repository_ref="synthetic/desired-state",
        base_branch="main",
        manifest_strategy=ManifestStrategy.PLAIN_KUBERNETES,
        manifest_root="apps/demo-api/deployment.yaml",
        application_ref="demo-api-production",
        allowed_change_types=frozenset({ChangeType.ROLLBACK_IMAGE, ChangeType.SCALE_REPLICAS}),
        allowed_resources=frozenset({"Deployment/demo-api"}),
        allowed_fields=frozenset({"spec.template.spec.containers[0].image", "spec.replicas"}),
        artifact_registry_allowlist=frozenset({"registry.example"}),
        max_replicas=5,
        verification_profile_ref="demo-api-health",
        known_good_images={"Deployment/demo-api": GOOD_IMAGE},
    )


def intent() -> ChangeIntent:
    return ChangeIntent(
        change_type=ChangeType.ROLLBACK_IMAGE,
        incident_id="incident-gitops-1",
        workflow_id="workflow-gitops-1",
        service="demo-api",
        environment="production",
        target_ref="Deployment/demo-api",
        reason_summary="Rollback the recent regression to known-good digest",
        evidence_ids=("evidence-current-1",),
        requested_by="investigator",
    )
