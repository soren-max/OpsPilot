from dataclasses import dataclass

from app.domain.change.models import (
    SHA256_IMAGE,
    ChangeIntent,
    ChangePolicyResult,
    ChangeRisk,
    ChangeSet,
    ChangeType,
    GitOpsApplicationProfile,
)


def _forbidden(rule: str, reason: str) -> ChangePolicyResult:
    return ChangePolicyResult(
        risk=ChangeRisk.FORBIDDEN,
        allowed=False,
        approval_required=False,
        rule=rule,
        reason=reason,
    )


@dataclass(frozen=True)
class ChangePolicyEngine:
    """Deterministic authority for semantic desired-state changes."""

    def assess_intent(
        self, intent: ChangeIntent, profile: GitOpsApplicationProfile
    ) -> ChangePolicyResult:
        if (intent.service, intent.environment) != (profile.service, profile.environment):
            return _forbidden("change.profile_scope", "Cross-service/environment change denied")
        if intent.change_type not in profile.allowed_change_types:
            return _forbidden("change.type_allowlist", "Change type is not operator-approved")
        if intent.target_ref not in profile.allowed_resources:
            return _forbidden("change.resource_allowlist", "Resource is not operator-approved")
        if not intent.evidence_ids:
            return _forbidden("change.evidence_required", "Current Evidence is required")
        if (
            intent.change_type is ChangeType.SCALE_REPLICAS
            and intent.requested_replicas is not None
            and intent.requested_replicas > profile.max_replicas
        ):
            return _forbidden("change.replica_bound", "Requested replicas exceed profile limit")
        return ChangePolicyResult(
            risk=ChangeRisk.HIGH,
            allowed=False,
            approval_required=True,
            rule="change.explicit_approval",
            reason="All desired-state changes require explicit OpsPilot approval",
        )

    def assess_change_set(
        self,
        intent: ChangeIntent,
        profile: GitOpsApplicationProfile,
        change_set: ChangeSet,
        *,
        approval_granted: bool,
    ) -> ChangePolicyResult:
        initial = self.assess_intent(intent, profile)
        if initial.risk is ChangeRisk.FORBIDDEN:
            return initial
        if change_set.blast_radius > profile.max_replicas:
            return _forbidden("change.blast_radius", "Affected replicas exceed operator limit")
        if (
            change_set.profile_id != profile.profile_id
            or change_set.service != intent.service
            or change_set.environment != intent.environment
            or change_set.evidence_ids != intent.evidence_ids
            or set(change_set.changed_files) != {profile.manifest_root}
            or len(change_set.mutations) != 1
        ):
            return _forbidden("change.correlation", "ChangeSet does not match intent and profile")
        for mutation in change_set.mutations:
            expected_field = (
                "spec.replicas"
                if intent.change_type is ChangeType.SCALE_REPLICAS
                else "spec.template.spec.containers[0].image"
            )
            if (
                mutation.resource_ref != intent.target_ref
                or mutation.mutation_type is not intent.change_type
                or mutation.field != expected_field
            ):
                return _forbidden("change.semantic_mismatch", "Mutation does not match intent")
            if (
                intent.change_type is ChangeType.SCALE_REPLICAS
                and mutation.after != intent.requested_replicas
            ):
                return _forbidden("change.semantic_mismatch", "Replicas do not match intent")
            if (
                intent.change_type is ChangeType.ROLLBACK_IMAGE
                and mutation.after != profile.known_good_images.get(intent.target_ref)
            ):
                return _forbidden(
                    "change.semantic_mismatch", "Artifact is not the operator known-good digest"
                )
            if mutation.resource_ref not in profile.allowed_resources:
                return _forbidden("change.resource_allowlist", "Planned resource is forbidden")
            if mutation.field not in profile.allowed_fields:
                return _forbidden("change.field_allowlist", "Planned field is forbidden")
            if mutation.mutation_type is ChangeType.ROLLBACK_IMAGE:
                image = str(mutation.after)
                if not SHA256_IMAGE.fullmatch(image):
                    return _forbidden("change.immutable_artifact", "Image must use sha256 digest")
                registry = image.split("/", 1)[0]
                if registry not in profile.artifact_registry_allowlist:
                    return _forbidden("change.registry_allowlist", "Image registry is forbidden")
            if mutation.mutation_type is ChangeType.SCALE_REPLICAS:
                replicas = int(mutation.after)
                if replicas < 0 or replicas > profile.max_replicas:
                    return _forbidden("change.replica_bound", "Replica count is outside bounds")
        return ChangePolicyResult(
            risk=ChangeRisk.HIGH,
            allowed=approval_granted,
            approval_required=True,
            rule="change.explicit_approval",
            reason=(
                "Approved semantic change is within the operator profile"
                if approval_granted
                else "Explicit OpsPilot approval is required"
            ),
        )
