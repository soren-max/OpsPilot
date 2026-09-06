from __future__ import annotations

import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.adapters.git import FakeGitChangeProvider
from app.adapters.gitops import FakeGitOpsReconciler
from app.change.service import ChangeDispatcher, ChangeService, ChangeWatcher
from app.db.base import Base, utc_now
from app.domain.change import (
    ChangeIntent,
    ChangeType,
    GitOpsApplicationProfile,
    GitOpsStatus,
    ManifestStrategy,
)
from app.domain.incidents.evidence import EvidenceType
from app.domain.incidents.models import IncidentStatus, Severity
from app.repositories import change_models, incident_models  # noqa: F401
from app.repositories.incident_models import EvidenceRecord, IncidentRecord

BAD = "registry.example/demo-api@sha256:" + "b" * 64
GOOD = "registry.example/demo-api@sha256:" + "a" * 64
PATH = "apps/demo-api/deployment.yaml"
MANIFEST = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-api
spec:
  replicas: 2
  selector:
    matchLabels: {{app: demo-api}}
  template:
    metadata:
      labels: {{app: demo-api}}
    spec:
      containers:
        - name: demo-api
          image: {BAD}
"""


class DemoVerifier:
    async def verify(self, incident_id: str, verification_profile_ref: str) -> bool:
        return incident_id == "incident-m9-demo" and verification_profile_ref == "demo-health"


def seed(db: Session) -> tuple[ChangeIntent, GitOpsApplicationProfile]:
    now = utc_now()
    incident = IncidentRecord(
        id="incident-m9-demo",
        title="demo-api deployment regression",
        summary="Synthetic current evidence shows elevated errors after deploy",
        severity=Severity.HIGH,
        status=IncidentStatus.MITIGATING,
        environment="gitops-lab",
        service="demo-api",
        source="synthetic-gitops-lab",
        created_by="demo-runner",
        tags=["m9", "synthetic"],
        version=1,
        created_at=now,
        updated_at=now,
    )
    evidence = EvidenceRecord(
        id="evidence-m9-current",
        incident=incident,
        evidence_type=EvidenceType.METRIC,
        source="synthetic-prometheus",
        source_reference="metric-template:error-rate",
        summary="Current error rate is above the synthetic threshold",
        observed_at=now,
        collected_at=now,
        collector="gitops-lab",
        evidence_metadata={},
        fingerprint="9" * 64,
    )
    db.add_all([incident, evidence])
    db.commit()
    profile = GitOpsApplicationProfile(
        profile_id="gitops-lab",
        service="demo-api",
        environment="gitops-lab",
        repository_ref="synthetic/desired-state",
        base_branch="main",
        manifest_strategy=ManifestStrategy.PLAIN_KUBERNETES,
        manifest_root=PATH,
        application_ref="demo-api",
        allowed_change_types=frozenset({ChangeType.ROLLBACK_IMAGE}),
        allowed_resources=frozenset({"Deployment/demo-api"}),
        allowed_fields=frozenset({"spec.template.spec.containers[0].image"}),
        artifact_registry_allowlist=frozenset({"registry.example"}),
        max_replicas=5,
        verification_profile_ref="demo-health",
        known_good_images={"Deployment/demo-api": GOOD},
    )
    intent = ChangeIntent(
        change_type=ChangeType.ROLLBACK_IMAGE,
        incident_id=incident.id,
        workflow_id="workflow-m9-demo",
        service="demo-api",
        environment="gitops-lab",
        target_ref="Deployment/demo-api",
        reason_summary="Rollback synthetic regression to operator-approved digest",
        evidence_ids=(evidence.id,),
        requested_by="investigator",
    )
    return intent, profile


async def run() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        intent, profile = seed(db)
        git = FakeGitChangeProvider(base_files={PATH: MANIFEST})
        service = ChangeService(db, git=git)
        print("[1/12] GitOps Lab ready")
        print("[2/12] Regression injected")
        print("[3/12] Incident created")
        print("[4/12] Evidence collected")
        record = service.propose(intent, profile)
        print("[5/12] Rollback proposed")
        print("[6/12] Policy requires approval")
        await service.approve(
            record.id,
            actor="synthetic-operator",
            reason="Current evidence supports this bounded desired-state rollback",
        )
        print("[7/12] Change approved")
        await ChangeDispatcher(db, git=git).dispatch_one()
        print("[8/12] Pull request created")
        assert record.pull_request_id
        # This object is deliberately outside ChangeService/GitChangeProvider.
        git.external_review(record.pull_request_id, approved=True)
        merged = git.external_merge(record.pull_request_id)
        print("[9/12] Pull request reviewed and merged (external synthetic reviewer)")
        reconciler = FakeGitOpsReconciler(
            GitOpsStatus(
                application_ref="demo-api",
                revision=merged,
                sync_status="Synced",
                health_status="Healthy",
                resources=("Deployment/demo-api",),
            )
        )
        await ChangeWatcher(db, git=git, gitops=reconciler, verifier=DemoVerifier()).poll(record.id)
        print("[10/12] Argo CD reconciled revision")
        print("[11/12] Verification passed")
        print("[12/12] Incident resolved")
        print()
        print(f"Incident: {intent.incident_id}")
        print(f"Change ID: {record.id}")
        print(f"PR: {record.pull_request_url}")
        print(f"Source revision: {record.source_revision}")
        print(f"Merged revision: {record.merged_revision}")
        print(f"Argo revision: {reconciler.status.revision}")
        print(f"Sync: {record.sync_status}")
        print(f"Health: {record.health_status}")
        print(f"Verification: {record.verification_status}")
        print(f"Final State: {record.status.value}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
