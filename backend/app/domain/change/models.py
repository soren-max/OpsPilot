from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@/-]{0,159}$")
SHA256_IMAGE = re.compile(
    r"^[a-z0-9][a-z0-9._/-]*(?::[0-9]+)?/[A-Za-z0-9._/-]+@sha256:[a-f0-9]{64}$"
)


class StrictChangeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ChangeType(StrEnum):
    ROLLBACK_IMAGE = "ROLLBACK_IMAGE"
    SCALE_REPLICAS = "SCALE_REPLICAS"


class ChangeStatus(StrEnum):
    PROPOSED = "PROPOSED"
    POLICY_APPROVED = "POLICY_APPROVED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    PLANNED = "PLANNED"
    VALIDATED = "VALIDATED"
    QUEUED = "QUEUED"
    BRANCH_CREATED = "BRANCH_CREATED"
    COMMITTED = "COMMITTED"
    PR_CREATED = "PR_CREATED"
    WAITING_REVIEW = "WAITING_REVIEW"
    APPROVED_FOR_MERGE = "APPROVED_FOR_MERGE"
    MERGED = "MERGED"
    RECONCILING = "RECONCILING"
    SYNCED = "SYNCED"
    HEALTHY = "HEALTHY"
    VERIFIED = "VERIFIED"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class ChangeRisk(StrEnum):
    HIGH = "HIGH"
    FORBIDDEN = "FORBIDDEN"


class ManifestStrategy(StrEnum):
    PLAIN_KUBERNETES = "PLAIN_KUBERNETES"


class ChangeIntent(StrictChangeModel):
    """Model/adapter-owned semantic request. Infrastructure coordinates are excluded."""

    change_type: ChangeType
    incident_id: Annotated[str, Field(min_length=1, max_length=64, pattern=SAFE_NAME.pattern)]
    workflow_id: Annotated[str, Field(min_length=1, max_length=64, pattern=SAFE_NAME.pattern)]
    service: Annotated[str, Field(min_length=1, max_length=120, pattern=SAFE_NAME.pattern)]
    environment: Annotated[str, Field(min_length=1, max_length=80, pattern=SAFE_NAME.pattern)]
    target_ref: Annotated[str, Field(min_length=1, max_length=160, pattern=SAFE_NAME.pattern)]
    reason_summary: Annotated[str, Field(min_length=3, max_length=1000)]
    evidence_ids: tuple[Annotated[str, Field(min_length=1, max_length=64)], ...]
    requested_by: Annotated[str, Field(min_length=1, max_length=80)]
    requested_replicas: Annotated[int, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def parameters_match_type(self) -> ChangeIntent:
        if not self.evidence_ids:
            raise ValueError("At least one current Evidence reference is required")
        if self.change_type is ChangeType.SCALE_REPLICAS and self.requested_replicas is None:
            raise ValueError("SCALE_REPLICAS requires requested_replicas")
        if self.change_type is ChangeType.ROLLBACK_IMAGE and self.requested_replicas is not None:
            raise ValueError("ROLLBACK_IMAGE cannot select replicas")
        return self


class GitOpsApplicationProfile(StrictChangeModel):
    """Operator-owned routing and mutation policy; never accepted from a change request."""

    profile_id: Annotated[str, Field(min_length=1, max_length=120, pattern=SAFE_NAME.pattern)]
    service: Annotated[str, Field(min_length=1, max_length=120, pattern=SAFE_NAME.pattern)]
    environment: Annotated[str, Field(min_length=1, max_length=80, pattern=SAFE_NAME.pattern)]
    repository_ref: Annotated[str, Field(min_length=3, max_length=240)]
    base_branch: Annotated[str, Field(min_length=1, max_length=120, pattern=SAFE_NAME.pattern)]
    manifest_strategy: ManifestStrategy = ManifestStrategy.PLAIN_KUBERNETES
    manifest_root: Annotated[str, Field(min_length=1, max_length=240)]
    application_ref: Annotated[str, Field(min_length=1, max_length=160, pattern=SAFE_NAME.pattern)]
    allowed_change_types: frozenset[ChangeType]
    allowed_resources: frozenset[str]
    allowed_fields: frozenset[str]
    artifact_registry_allowlist: frozenset[str]
    max_replicas: Annotated[int, Field(ge=1, le=10_000)]
    verification_profile_ref: Annotated[
        str, Field(min_length=1, max_length=120, pattern=SAFE_NAME.pattern)
    ]
    known_good_images: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_operator_profile(self) -> GitOpsApplicationProfile:
        if self.manifest_root.startswith(("/", "../")) or "/../" in self.manifest_root:
            raise ValueError("manifest_root must be a repository-relative bounded path")
        for image in self.known_good_images.values():
            if not SHA256_IMAGE.fullmatch(image):
                raise ValueError("known-good images must use immutable sha256 digests")
        return self


class SemanticMutation(StrictChangeModel):
    resource_ref: str
    mutation_type: ChangeType
    field: str
    before: str | int
    after: str | int
    artifact_digest: str | None = None


class ChangeSet(StrictChangeModel):
    change_id: str
    profile_id: str
    service: str
    environment: str
    source_revision: str
    target_revision: str | None = None
    mutations: tuple[SemanticMutation, ...]
    blast_radius: int = Field(ge=0)
    evidence_ids: tuple[str, ...]
    changed_files: dict[str, str]
    raw_diff: str


class VerificationPlan(StrictChangeModel):
    profile_ref: str
    signals: tuple[str, ...] = ("health", "metrics", "logs")


class ChangePreview(StrictChangeModel):
    resource: str
    field: str
    before: str | int
    after: str | int
    blast_radius: int
    artifact: str | None
    environment: str
    verification_plan: VerificationPlan
    raw_diff: str


class ChangePolicyResult(StrictChangeModel):
    risk: ChangeRisk
    allowed: bool
    approval_required: bool
    rule: str
    reason: str


class PullRequestState(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    MERGED = "MERGED"


class ReviewState(StrEnum):
    WAITING = "WAITING"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class PullRequest(StrictChangeModel):
    pull_request_id: str
    url: str
    branch: str
    head_revision: str
    state: PullRequestState
    review_state: ReviewState
    merged_revision: str | None = None


class GitOpsStatus(StrictChangeModel):
    application_ref: str
    revision: str | None
    sync_status: str
    health_status: str
    resources: tuple[str, ...] = ()


class RevertProposal(StrictChangeModel):
    original_change_id: str
    incident_id: str
    reason_summary: str
    evidence_ids: tuple[str, ...]
    requested_by: str
    created_at: datetime
