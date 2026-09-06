from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta

from opentelemetry import metrics, trace
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.incident_service import safe_audit_metadata
from app.change.planner import PlainKubernetesChangePlanner
from app.db.base import utc_now
from app.domain.audit.models import ActorType, AuditEventType
from app.domain.change import (
    ChangeIntent,
    ChangePolicyEngine,
    ChangePreview,
    ChangeSet,
    ChangeStatus,
    ChangeVerifier,
    GitChangeProvider,
    GitOpsApplicationProfile,
    GitOpsReconciler,
    PullRequestState,
    ReviewState,
    VerificationPlan,
)
from app.domain.incidents.models import IncidentStatus
from app.repositories.change_models import (
    ChangeOutboxRecord,
    ChangeOutboxStatus,
    ChangeRecord,
)
from app.repositories.changes import ChangeOutboxRepository, ChangeRepository
from app.repositories.incident_models import (
    EvidenceRecord,
    IncidentAuditEventRecord,
    IncidentRecord,
)
from app.repositories.incidents import AuditEventRepository
from app.services.redaction import redact_text

tracer = trace.get_tracer("opspilot.change")
meter = metrics.get_meter("opspilot.change")
change_total = meter.create_counter("opspilot_change_total")
change_pr_total = meter.create_counter("opspilot_change_pr_total")
change_rejected_total = meter.create_counter("opspilot_change_rejected_total")
change_reconciliation_total = meter.create_counter("opspilot_change_reconciliation_total")
change_unknown_total = meter.create_counter("opspilot_change_unknown_total")
change_verification_failure_total = meter.create_counter(
    "opspilot_change_verification_failure_total"
)
change_duration = meter.create_histogram("opspilot_change_duration_seconds", unit="s")
change_review_wait = meter.create_histogram("opspilot_change_review_wait_seconds", unit="s")
gitops_reconcile = meter.create_histogram("opspilot_gitops_reconcile_seconds", unit="s")


def action_fingerprint(intent: ChangeIntent) -> str:
    payload = intent.model_dump(mode="json", exclude={"requested_by"})
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def plan_fingerprint(plan: ChangeSet) -> str:
    return hashlib.sha256(
        json.dumps(plan.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()


class ChangeService:
    def __init__(
        self,
        db: Session,
        *,
        git: GitChangeProvider | None,
        policy: ChangePolicyEngine | None = None,
        planner: PlainKubernetesChangePlanner | None = None,
    ) -> None:
        self.db = db
        self.git = git
        self.policy = policy or ChangePolicyEngine()
        self.planner = planner or PlainKubernetesChangePlanner()
        self.changes = ChangeRepository(db)
        self.outbox = ChangeOutboxRepository(db)
        self.audits = AuditEventRepository(db)

    def propose(self, intent: ChangeIntent, profile: GitOpsApplicationProfile) -> ChangeRecord:
        incident = self.db.get(IncidentRecord, intent.incident_id)
        if incident is None:
            raise ValueError("Incident does not exist")
        if (incident.service, incident.environment) != (intent.service, intent.environment):
            raise ValueError("Change crosses the Incident service/environment boundary")
        self._current_evidence(intent, profile)
        evidence = {
            item.id
            for item in self.db.query(EvidenceRecord).filter(
                EvidenceRecord.incident_id == intent.incident_id,
                EvidenceRecord.id.in_(intent.evidence_ids),
            )
        }
        if evidence != set(intent.evidence_ids):
            raise ValueError("Change references unknown or cross-Incident Evidence")
        fingerprint = action_fingerprint(intent)
        existing = self.changes.find_action(intent.workflow_id, fingerprint)
        if existing is not None:
            return existing
        assessment = self.policy.assess_intent(intent, profile)
        now = utc_now()
        record = ChangeRecord(
            incident_id=intent.incident_id,
            workflow_id=intent.workflow_id,
            action_fingerprint=fingerprint,
            profile_id=profile.profile_id,
            change_type=intent.change_type,
            status=(
                ChangeStatus.WAITING_APPROVAL
                if assessment.approval_required
                else ChangeStatus.REJECTED
            ),
            gitops_application_ref=profile.application_ref,
            policy_result_ref=str(uuid.uuid4()),
            intent_payload=intent.model_dump(mode="json"),
            profile_payload=profile.model_dump(mode="json"),
            policy_payload=assessment.model_dump(mode="json"),
            created_at=now,
            updated_at=now,
            version=1,
        )
        try:
            self.changes.add(record)
            self.db.flush()
            self._audit(record, AuditEventType.CHANGE_PROPOSED, "Semantic change proposed")
            self._audit(
                record,
                AuditEventType.CHANGE_POLICY_ASSESSED,
                "Deterministic change policy assessed",
                {"risk": assessment.risk.value, "rule": assessment.rule},
            )
            if assessment.approval_required:
                self._audit(
                    record,
                    AuditEventType.CHANGE_APPROVAL_REQUESTED,
                    "Explicit OpsPilot approval requested",
                )
            else:
                change_rejected_total.add(1, {"rule": assessment.rule})
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            duplicate = self.changes.find_action(intent.workflow_id, fingerprint)
            if duplicate is None:
                raise
            return duplicate
        change_total.add(1, {"change.type": intent.change_type.value})
        return record

    def _current_evidence(self, intent: ChangeIntent, profile: GitOpsApplicationProfile) -> None:
        now = utc_now()
        records = list(
            self.db.query(EvidenceRecord).filter(
                EvidenceRecord.incident_id == intent.incident_id,
                EvidenceRecord.id.in_(intent.evidence_ids),
            )
        )
        if {item.id for item in records} != set(intent.evidence_ids):
            raise ValueError("Change references unknown or cross-Incident Evidence")
        for item in records:
            if (
                not 0
                <= (now - item.observed_at).total_seconds()
                <= profile.evidence_max_age_seconds
            ):
                raise ValueError("Change requires fresh current Evidence")

    async def prepare(self, change_id: str) -> ChangeRecord:
        if self.git is None:
            raise ValueError("Git provider is not configured")
        record = self._require(change_id, lock=True)
        if record.status is not ChangeStatus.WAITING_APPROVAL:
            return record
        intent = ChangeIntent.model_validate_json(json.dumps(record.intent_payload))
        profile = GitOpsApplicationProfile.model_validate_json(json.dumps(record.profile_payload))
        self._current_evidence(intent, profile)
        source = await self.git.read_base_revision()
        planned = self.planner.plan(
            change_id=record.id,
            intent=intent,
            profile=profile,
            source_revision=source,
            manifests={
                profile.manifest_root: await self.git.read_file(profile.manifest_root, source)
            },
        )
        assessment = self.policy.assess_change_set(intent, profile, planned, approval_granted=False)
        if assessment.risk.value == "FORBIDDEN":
            raise ValueError(assessment.reason)
        record.source_revision = source
        record.change_set_payload = planned.model_dump(mode="json")
        record.updated_at = utc_now()
        record.version += 1
        self._audit(
            record, AuditEventType.CHANGE_PLANNED, "Semantic preview prepared before approval"
        )
        self.db.commit()
        return record

    async def approve(
        self, change_id: str, *, actor: str, reason: str, expected_plan: str | None = None
    ) -> ChangeRecord:
        if self.git is None:
            raise ValueError("Git provider is not configured")
        record = self._require(change_id, lock=True)
        if record.status is not ChangeStatus.WAITING_APPROVAL:
            if record.approval_actor == actor and record.status not in {
                ChangeStatus.REJECTED,
                ChangeStatus.FAILED,
            }:
                return record
            raise ValueError("Change is not waiting for approval")
        intent = ChangeIntent.model_validate_json(json.dumps(record.intent_payload))
        if len(reason.strip()) < 3 or not actor.strip():
            raise ValueError("Approval requires an actor and a meaningful reason")
        if actor == intent.requested_by:
            raise ValueError("Change requester cannot approve their own proposal")
        profile = GitOpsApplicationProfile.model_validate_json(json.dumps(record.profile_payload))
        self._current_evidence(intent, profile)
        source_revision = await self.git.read_base_revision()
        manifest = await self.git.read_file(profile.manifest_root, source_revision)
        planned = self.planner.plan(
            change_id=record.id,
            intent=intent,
            profile=profile,
            source_revision=source_revision,
            manifests={profile.manifest_root: manifest},
        )
        if (
            record.change_set_payload is not None
            and record.change_set_payload != planned.model_dump(mode="json")
        ):
            raise ValueError("Desired state changed since preview; prepare and review a new plan")
        if expected_plan is not None and expected_plan != plan_fingerprint(planned):
            raise ValueError("Approval does not match the reviewed semantic plan")
        assessment = self.policy.assess_change_set(intent, profile, planned, approval_granted=True)
        if not assessment.allowed:
            record.status = ChangeStatus.REJECTED
            record.policy_payload = assessment.model_dump(mode="json")
            record.failure_category = assessment.rule
            record.safe_failure_message = assessment.reason
            record.updated_at = utc_now()
            record.version += 1
            self.db.commit()
            change_rejected_total.add(1, {"rule": assessment.rule})
            return record
        now = utc_now()
        record.status = ChangeStatus.QUEUED
        record.approval_id = str(uuid.uuid4())
        record.approval_actor = actor
        record.approval_reason = (redact_text(reason) or "")[:500]
        record.approval_decided_at = now
        record.source_revision = source_revision
        record.branch = f"opspilot/change/{record.id}"
        record.change_set_payload = planned.model_dump(mode="json")
        record.policy_payload = assessment.model_dump(mode="json")
        record.updated_at = now
        record.version += 1
        self.outbox.add(
            ChangeOutboxRecord(
                change_id=record.id,
                message_type="change.create_pull_request",
                status=ChangeOutboxStatus.PENDING,
                attempts=0,
                available_at=now,
                created_at=now,
            )
        )
        self._audit(
            record,
            AuditEventType.CHANGE_APPROVED,
            "OpsPilot approval granted",
            {"reason": reason[:500]},
            actor_type=ActorType.HUMAN,
            actor_id=actor,
        )
        self._audit(record, AuditEventType.CHANGE_PLANNED, "Semantic ChangeSet planned")
        self._audit(record, AuditEventType.CHANGE_VALIDATED, "Manifest and profile validated")
        self._audit(record, AuditEventType.CHANGE_QUEUED, "Change and outbox committed atomically")
        self.db.commit()
        return record

    def reject(self, change_id: str, *, actor: str, reason: str) -> ChangeRecord:
        record = self._require(change_id, lock=True)
        if record.status is not ChangeStatus.WAITING_APPROVAL:
            raise ValueError("Change is not waiting for approval")
        record.status = ChangeStatus.REJECTED
        record.approval_actor = actor
        record.approval_reason = (redact_text(reason) or "")[:500]
        record.approval_decided_at = utc_now()
        record.safe_failure_message = (redact_text(reason) or "")[:500]
        record.updated_at = utc_now()
        record.version += 1
        change_rejected_total.add(1, {"rule": "human.rejected"})
        self._audit(
            record,
            AuditEventType.APPROVAL_REJECTED,
            "GitOps change rejected at OpsPilot approval gate",
            {"reason": reason[:500]},
            actor_type=ActorType.HUMAN,
            actor_id=actor,
        )
        self.db.commit()
        return record

    def preview(self, record: ChangeRecord) -> ChangePreview | None:
        if record.change_set_payload is None:
            return None
        change_set = ChangeSet.model_validate_json(json.dumps(record.change_set_payload))
        mutation = change_set.mutations[0]
        profile = GitOpsApplicationProfile.model_validate_json(json.dumps(record.profile_payload))
        return ChangePreview(
            resource=mutation.resource_ref,
            field=mutation.field,
            before=mutation.before,
            after=mutation.after,
            blast_radius=change_set.blast_radius,
            artifact=mutation.artifact_digest,
            environment=change_set.environment,
            verification_plan=VerificationPlan(profile_ref=profile.verification_profile_ref),
            raw_diff=change_set.raw_diff,
            plan_fingerprint=plan_fingerprint(change_set),
        )

    def _require(self, change_id: str, *, lock: bool = False) -> ChangeRecord:
        item = self.changes.get(change_id, lock=lock)
        if item is None:
            raise ValueError("Change does not exist")
        return item

    def _audit(
        self,
        record: ChangeRecord,
        event_type: AuditEventType,
        summary: str,
        extra: dict[str, str] | None = None,
        *,
        actor_type: ActorType = ActorType.SYSTEM,
        actor_id: str = "change-workflow",
    ) -> None:
        self.audits.append(
            IncidentAuditEventRecord(
                incident_id=record.incident_id,
                event_type=event_type,
                actor_type=actor_type,
                actor_id=actor_id,
                correlation_id=record.workflow_id,
                occurred_at=utc_now(),
                payload_summary=summary,
                event_metadata=safe_audit_metadata(
                    {"change_id": record.id, "profile_id": record.profile_id, **(extra or {})}
                ),
            )
        )


class ChangeDispatcher:
    def __init__(self, db: Session, *, git: GitChangeProvider, lease_seconds: int = 60) -> None:
        self.db = db
        self.git = git
        self.lease_seconds = lease_seconds
        self.changes = ChangeRepository(db)
        self.outbox = ChangeOutboxRepository(db)
        self.service = ChangeService(db, git=git)

    def recover_expired_dispatches(self) -> int:
        """Treat a lost dispatch lease as indeterminate; never replay a possible Git write."""

        recovered = 0
        for message in self.outbox.expired_claims(now=utc_now()):
            record = self.service._require(message.change_id, lock=True)
            if record.status in {
                ChangeStatus.QUEUED,
                ChangeStatus.BRANCH_CREATED,
                ChangeStatus.COMMITTED,
                ChangeStatus.PR_CREATED,
            }:
                record.status = ChangeStatus.UNKNOWN
                record.failure_category = "INDETERMINATE_GIT_SIDE_EFFECT"
                record.safe_failure_message = (
                    "Git dispatch lease expired; automatic redispatch is disabled"
                )
                record.updated_at = utc_now()
                record.version += 1
                change_unknown_total.add(1)
                self.service._audit(
                    record,
                    AuditEventType.CHANGE_RECONCILIATION_REQUIRED,
                    "Git dispatch lease expired with an indeterminate side effect",
                )
            message.status = ChangeOutboxStatus.INDETERMINATE
            message.completed_at = utc_now()
            recovered += 1
        if recovered:
            self.db.commit()
        return recovered

    async def dispatch_one(self, *, change_id: str | None = None) -> bool:
        now = utc_now()
        message = self.outbox.claim_one(
            now=now, claimed_until=now + timedelta(seconds=self.lease_seconds), change_id=change_id
        )
        if message is None:
            return False
        record = self.service._require(message.change_id, lock=True)
        if record.status is not ChangeStatus.QUEUED:
            message.status = ChangeOutboxStatus.COMPLETED
            message.completed_at = now
            self.db.commit()
            return True
        # A durable claim precedes every possible external write. A process crash must
        # leave CLAIMED, never PENDING. Subsequent dispatchers cannot replay this message.
        self.db.commit()
        record = self.service._require(message.change_id, lock=True)
        assert record.branch and record.source_revision and record.change_set_payload
        intent = ChangeIntent.model_validate_json(json.dumps(record.intent_payload))
        profile = GitOpsApplicationProfile.model_validate_json(json.dumps(record.profile_payload))
        change_set = ChangeSet.model_validate_json(json.dumps(record.change_set_payload))
        try:
            self.service._current_evidence(intent, profile)
            assessment = self.service.policy.assess_change_set(
                intent, profile, change_set, approval_granted=bool(record.approval_id)
            )
            if (
                not assessment.allowed
                or not record.approval_decided_at
                or (utc_now() - record.approval_decided_at).total_seconds()
                > profile.approval_max_age_seconds
                or action_fingerprint(intent) != record.action_fingerprint
                or await self.git.read_base_revision() != record.source_revision
            ):
                raise ValueError("Approved change is stale or no longer authorized")
            # Re-plan to prove the durable bytes still match the approved semantic intent.
            replanned = self.service.planner.plan(
                change_id=record.id,
                intent=intent,
                profile=profile,
                source_revision=record.source_revision,
                manifests={
                    profile.manifest_root: await self.git.read_file(
                        profile.manifest_root, record.source_revision
                    )
                },
            )
            if replanned != change_set:
                raise ValueError("Durable ChangeSet does not match the approved intent")
        except ValueError:
            record.status = ChangeStatus.REJECTED
            record.safe_failure_message = "Change authorization or desired-state validation failed"
            message.status = ChangeOutboxStatus.COMPLETED
            self.db.commit()
            return True
        try:
            with tracer.start_as_current_span("change.git.create_pr") as span:
                span.set_attribute("change.id", record.id)
                span.set_attribute("profile.id", record.profile_id)
                await self.git.create_branch(record.branch, record.source_revision)
                record.status = ChangeStatus.BRANCH_CREATED
                self.service._audit(
                    record, AuditEventType.GIT_BRANCH_CREATED, "Deterministic branch created"
                )
                self.db.commit()
                record = self.service._require(record.id, lock=True)
                assert record.branch
                message_text = _commit_message(record, intent)
                record.commit_sha = await self.git.commit_changes(
                    record.branch, change_set.changed_files, message_text
                )
                record.status = ChangeStatus.COMMITTED
                self.service._audit(record, AuditEventType.GIT_COMMIT_CREATED, "Change committed")
                self.db.commit()
                record = self.service._require(record.id, lock=True)
                assert record.branch
                pull = await self.git.create_pull_request(
                    record.branch,
                    f"change: {intent.change_type.value.lower()} {intent.service}",
                    _pull_request_body(record, intent, profile, change_set),
                )
        except Exception:
            # HTTP 5xx, malformed success payloads and connection failures can all
            # follow an accepted write. No automatic retry is safe without proof.
            record.status = ChangeStatus.UNKNOWN
            record.failure_category = "INDETERMINATE_GIT_SIDE_EFFECT"
            record.safe_failure_message = (
                "Git operation outcome indeterminate; automatic redispatch disabled"
            )
            record.updated_at = utc_now()
            record.version += 1
            message.status = ChangeOutboxStatus.INDETERMINATE
            message.completed_at = utc_now()
            change_unknown_total.add(1)
            self.service._audit(
                record,
                AuditEventType.CHANGE_RECONCILIATION_REQUIRED,
                "Git operation outcome indeterminate",
            )
            self.db.commit()
            return True
        record.pull_request_id = pull.pull_request_id
        record.pull_request_url = pull.url
        record.review_state = pull.review_state.value
        record.status = ChangeStatus.WAITING_REVIEW
        record.updated_at = utc_now()
        record.version += 1
        message.status = ChangeOutboxStatus.COMPLETED
        message.completed_at = utc_now()
        self.service._audit(record, AuditEventType.PULL_REQUEST_CREATED, "Pull request created")
        change_pr_total.add(1, {"change.type": record.change_type.value})
        self.db.commit()
        return True

    async def reconcile_unknown(self, change_id: str) -> ChangeRecord:
        record = self.service._require(change_id, lock=True)
        if (
            record.status not in {ChangeStatus.UNKNOWN, ChangeStatus.RECONCILIATION_REQUIRED}
            or record.branch is None
        ):
            raise ValueError("Change is not awaiting Git side-effect reconciliation")
        pull = await self.git.find_pull_request(record.branch, record.id)
        change_reconciliation_total.add(1)
        if pull is None:
            record.status = ChangeStatus.RECONCILIATION_REQUIRED
            self.service._audit(
                record,
                AuditEventType.CHANGE_RECONCILIATION_REQUIRED,
                "Git side effect could not be proven",
            )
        else:
            if (
                not record.commit_sha
                or pull.head_revision != record.commit_sha
                or pull.branch != record.branch
            ):
                record.status = ChangeStatus.RECONCILIATION_REQUIRED
                record.safe_failure_message = (
                    "Recovered PR does not match the durable approved commit"
                )
                self.db.commit()
                return record
            record.pull_request_id = pull.pull_request_id
            record.pull_request_url = pull.url
            record.review_state = pull.review_state.value
            record.status = ChangeStatus.WAITING_REVIEW
            record.failure_category = None
            record.safe_failure_message = None
            self.service._audit(
                record, AuditEventType.PULL_REQUEST_CREATED, "Existing correlated PR recovered"
            )
        record.updated_at = utc_now()
        record.version += 1
        self.db.commit()
        return record


class ChangeWatcher:
    def __init__(
        self,
        db: Session,
        *,
        git: GitChangeProvider,
        gitops: GitOpsReconciler,
        verifier: ChangeVerifier,
    ) -> None:
        self.db = db
        self.git = git
        self.gitops = gitops
        self.verifier = verifier
        self.changes = ChangeRepository(db)
        self.service = ChangeService(db, git=git)

    async def poll(self, change_id: str) -> ChangeRecord:
        record = self.service._require(change_id, lock=True)
        if record.status in {
            ChangeStatus.RESOLVED,
            ChangeStatus.FAILED,
            ChangeStatus.REJECTED,
            ChangeStatus.RECONCILIATION_REQUIRED,
        }:
            return record
        if record.pull_request_id is None:
            raise ValueError("Change has no pull request")
        pull = await self.git.get_pull_request(record.pull_request_id)
        if pull.head_revision != record.commit_sha or pull.branch != record.branch:
            return self._reconciliation_required(record, "Pull request head revision changed")
        if pull.state is PullRequestState.CLOSED:
            record.status = ChangeStatus.REJECTED
            record.safe_failure_message = "Pull request closed without merge"
            self.service._audit(
                record,
                AuditEventType.PULL_REQUEST_REVIEWED,
                "Pull request closed without merge",
            )
            record.updated_at = utc_now()
            self.db.commit()
            return record
        if pull.state is not PullRequestState.MERGED:
            record.review_state = pull.review_state.value
            if pull.review_state is ReviewState.APPROVED:
                first_approval_observation = record.status is not ChangeStatus.APPROVED_FOR_MERGE
                record.status = ChangeStatus.APPROVED_FOR_MERGE
                if first_approval_observation:
                    change_review_wait.record(
                        max(0.0, (utc_now() - record.created_at).total_seconds())
                    )
                    self.service._audit(
                        record,
                        AuditEventType.PULL_REQUEST_REVIEWED,
                        "External Git review approved; OpsPilot still cannot merge",
                    )
            elif pull.review_state is ReviewState.CHANGES_REQUESTED:
                record.status = ChangeStatus.WAITING_REVIEW
                self.service._audit(
                    record,
                    AuditEventType.PULL_REQUEST_REVIEWED,
                    "External Git review requested changes",
                )
            else:
                record.status = ChangeStatus.WAITING_REVIEW
            record.updated_at = utc_now()
            record.version += 1
            self.db.commit()
            return record
        if pull.merged_revision is None:
            return self._reconciliation_required(record, "Merged PR lacks a revision")
        if record.merged_revision is not None and record.merged_revision != pull.merged_revision:
            return self._reconciliation_required(record, "Observed merge revision changed")
        profile = GitOpsApplicationProfile.model_validate_json(json.dumps(record.profile_payload))
        change_set = ChangeSet.model_validate_json(json.dumps(record.change_set_payload))
        if pull.review_state is not ReviewState.APPROVED:
            return self._reconciliation_required(
                record, "Merged PR lacks current external review approval"
            )
        # Squash and merge commits can differ from the PR head. Verify exact desired
        # bytes at the observed merged SHA instead of trusting a mutable branch.
        for path, expected in change_set.changed_files.items():
            if await self.git.read_file(path, pull.merged_revision) != expected:
                return self._reconciliation_required(
                    record, "Merged revision does not contain approved desired state"
                )
        record.review_state = pull.review_state.value
        if record.merged_revision is None:
            record.merged_revision = pull.merged_revision
            record.status = ChangeStatus.MERGED
            self.service._audit(record, AuditEventType.PULL_REQUEST_MERGED, "Pull request merged")
            self.service._audit(
                record,
                AuditEventType.GITOPS_RECONCILIATION_STARTED,
                "Waiting for pull-based reconciliation",
            )
        started = utc_now()
        gitops_status = await self.gitops.get_application_status(record.gitops_application_ref)
        gitops_reconcile.record(max(0.0, (utc_now() - started).total_seconds()))
        if gitops_status.application_ref != record.gitops_application_ref:
            return self._reconciliation_required(record, "Argo CD application mismatch")
        record.gitops_revision = gitops_status.revision
        record.sync_status = gitops_status.sync_status
        record.health_status = gitops_status.health_status
        if gitops_status.revision != record.merged_revision:
            if gitops_status.sync_status.lower() == "synced":
                return self._reconciliation_required(record, "Argo CD revision mismatch")
            record.status = ChangeStatus.RECONCILING
            record.updated_at = utc_now()
            self.db.commit()
            return record
        if gitops_status.sync_status.lower() != "synced":
            record.status = ChangeStatus.RECONCILING
            record.updated_at = utc_now()
            self.db.commit()
            return record
        if record.status is not ChangeStatus.SYNCED:
            self.service._audit(record, AuditEventType.GITOPS_SYNCED, "Argo CD reports Synced")
        record.status = ChangeStatus.SYNCED
        if gitops_status.health_status.lower() != "healthy":
            record.updated_at = utc_now()
            self.db.commit()
            return record
        record.status = ChangeStatus.HEALTHY
        self.service._audit(record, AuditEventType.GITOPS_HEALTHY, "Argo CD reports Healthy")
        profile = GitOpsApplicationProfile.model_validate_json(json.dumps(record.profile_payload))
        with tracer.start_as_current_span("change.verify"):
            verified = await self.verifier.verify(
                record.incident_id, profile.verification_profile_ref
            )
        record.verification_id = record.verification_id or str(uuid.uuid4())
        record.verification_status = "SUCCEEDED" if verified else "FAILED"
        if not verified:
            record.status = ChangeStatus.FAILED
            record.failure_category = "INDEPENDENT_VERIFICATION_FAILED"
            record.safe_failure_message = (
                "GitOps applied successfully but current-state verification failed"
            )
            change_verification_failure_total.add(1)
            self.service._audit(
                record,
                AuditEventType.CHANGE_VERIFICATION_FAILED,
                "GitOps healthy but independent verification failed",
            )
        else:
            record.status = ChangeStatus.RESOLVED
            incident = self.db.get(IncidentRecord, record.incident_id)
            if incident is not None:
                incident.status = IncidentStatus.RESOLVED
                incident.resolved_at = utc_now()
                incident.version += 1
            self.service._audit(record, AuditEventType.CHANGE_VERIFIED, "Change verified")
            self.service._audit(record, AuditEventType.CHANGE_RESOLVED, "Incident resolved")
            change_duration.record(max(0.0, (utc_now() - record.created_at).total_seconds()))
        record.updated_at = utc_now()
        record.version += 1
        self.db.commit()
        return record

    def _reconciliation_required(self, record: ChangeRecord, reason: str) -> ChangeRecord:
        record.status = ChangeStatus.RECONCILIATION_REQUIRED
        record.failure_category = "REVISION_MISMATCH"
        record.safe_failure_message = reason
        record.updated_at = utc_now()
        record.version += 1
        change_reconciliation_total.add(1)
        self.service._audit(record, AuditEventType.CHANGE_RECONCILIATION_REQUIRED, reason)
        self.db.commit()
        return record


def _commit_message(record: ChangeRecord, intent: ChangeIntent) -> str:
    return (
        f"change(gitops): {intent.change_type.value.lower()} {intent.service}\n\n"
        f"OpsPilot-Change-ID: {record.id}\n"
        f"Incident-ID: {record.incident_id}\n"
        f"Workflow-ID: {record.workflow_id}\n"
    )


def _pull_request_body(
    record: ChangeRecord,
    intent: ChangeIntent,
    profile: GitOpsApplicationProfile,
    change_set: ChangeSet,
) -> str:
    mutation = change_set.mutations[0]
    evidence = ", ".join(change_set.evidence_ids)
    return f"""## Governed GitOps change

Incident: {record.incident_id}
Service: {intent.service}
Environment: {intent.environment}
Change Summary: {redact_text(intent.reason_summary)}
Current Evidence: {evidence}

## Semantic Diff

- Resource: {mutation.resource_ref}
- Field: {mutation.field}
- Before: {mutation.before}
- After: {mutation.after}
- Blast Radius: {change_set.blast_radius}

Risk: HIGH
Approval Reference: {record.approval_id}
Verification Plan: {profile.verification_profile_ref}
Rollback / Revert Strategy: Create a new governed RevertProposal and PR.

OpsPilot Change ID: {record.id}
"""
