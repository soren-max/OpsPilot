from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any

import yaml  # type: ignore[import-untyped]

from app.domain.change import (
    ChangeIntent,
    ChangeSet,
    ChangeType,
    GitOpsApplicationProfile,
    SemanticMutation,
)


class ChangePlanningError(ValueError):
    pass


FORBIDDEN_KINDS = frozenset(
    {
        "Secret",
        "ServiceAccount",
        "ClusterRole",
        "ClusterRoleBinding",
        "RoleBinding",
        "MutatingWebhookConfiguration",
        "ValidatingWebhookConfiguration",
        "CustomResourceDefinition",
        "Namespace",
    }
)
FORBIDDEN_REPOSITORY_PATHS = frozenset(
    {".github/workflows", "CODEOWNERS", ".opspilot", "opspilot-policy"}
)


def _documents(content: str) -> list[dict[str, Any]]:
    try:
        loaded = list(yaml.safe_load_all(content))
    except yaml.YAMLError as exc:
        raise ChangePlanningError("Manifest YAML is invalid") from exc
    if not loaded or any(not isinstance(item, dict) for item in loaded):
        raise ChangePlanningError("Manifest must contain Kubernetes objects")
    return loaded


def _resource_ref(document: dict[str, Any]) -> str:
    metadata = document.get("metadata")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("name"), str):
        raise ChangePlanningError("Kubernetes resource metadata.name is required")
    kind = document.get("kind")
    api_version = document.get("apiVersion")
    if not isinstance(kind, str) or not isinstance(api_version, str):
        raise ChangePlanningError("Kubernetes apiVersion and kind are required")
    return f"{kind}/{metadata['name']}"


def _validate_safe_document(document: dict[str, Any]) -> None:
    kind = str(document.get("kind", ""))
    if kind in FORBIDDEN_KINDS:
        raise ChangePlanningError(f"Changes to {kind} are forbidden")
    serialized = yaml.safe_dump(document, sort_keys=True)
    forbidden_fragments = (
        "hostPath:",
        "hostNetwork: true",
        "hostPID: true",
        "privileged: true",
        "allowPrivilegeEscalation: true",
    )
    if any(item in serialized for item in forbidden_fragments):
        raise ChangePlanningError("Privileged workload fields are forbidden")
    if kind != "Deployment":
        raise ChangePlanningError("M9 supports bounded Deployment mutations only")
    spec = document.get("spec")
    template = spec.get("template") if isinstance(spec, dict) else None
    pod_spec = template.get("spec") if isinstance(template, dict) else None
    if not isinstance(pod_spec, dict):
        raise ChangePlanningError("Deployment pod specification is required")
    volumes = pod_spec.get("volumes", [])
    if isinstance(volumes, list) and any(
        isinstance(volume, dict) and "secret" in volume for volume in volumes
    ):
        raise ChangePlanningError("Secret-backed volumes are forbidden in change targets")
    containers = pod_spec.get("containers")
    if not isinstance(containers, list) or not containers:
        raise ChangePlanningError("Deployment containers are required")
    for container in containers:
        if not isinstance(container, dict):
            raise ChangePlanningError("Deployment container entries must be objects")
        if "command" in container or "args" in container:
            raise ChangePlanningError("Command and argument-bearing workloads are forbidden")
        environment = container.get("env", [])
        if isinstance(environment, list) and any(
            isinstance(item, dict)
            and isinstance(item.get("valueFrom"), dict)
            and "secretKeyRef" in item["valueFrom"]
            for item in environment
        ):
            raise ChangePlanningError("Secret-derived environment variables are forbidden")


@dataclass(frozen=True)
class PlainKubernetesChangePlanner:
    """Pure semantic planner. It is neither an agent nor an authorization boundary."""

    def plan(
        self,
        *,
        change_id: str,
        intent: ChangeIntent,
        profile: GitOpsApplicationProfile,
        source_revision: str,
        manifests: dict[str, str],
    ) -> ChangeSet:
        if not manifests:
            raise ChangePlanningError("No desired-state manifests were loaded")
        matches: list[tuple[str, list[dict[str, Any]], int]] = []
        for path, content in manifests.items():
            if path.startswith(("/", "../")) or any(
                marker in path for marker in FORBIDDEN_REPOSITORY_PATHS
            ):
                raise ChangePlanningError("Manifest path is outside the operator-owned scope")
            docs = _documents(content)
            for index, document in enumerate(docs):
                if _resource_ref(document) == intent.target_ref:
                    matches.append((path, docs, index))
        if len(matches) != 1:
            raise ChangePlanningError("Target resource did not resolve uniquely")
        path, docs, index = matches[0]
        target = docs[index]
        _validate_safe_document(target)
        before_content = manifests[path]
        mutation = self._mutate(intent, profile, target)
        _validate_safe_document(target)
        after_content = yaml.safe_dump_all(docs, sort_keys=False)
        raw_diff = "".join(
            difflib.unified_diff(
                before_content.splitlines(keepends=True),
                after_content.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )
        if not raw_diff:
            raise ChangePlanningError("Requested change already matches desired state")
        replicas = target.get("spec", {}).get("replicas", 1)
        return ChangeSet(
            change_id=change_id,
            profile_id=profile.profile_id,
            service=intent.service,
            environment=intent.environment,
            source_revision=source_revision,
            mutations=(mutation,),
            blast_radius=int(replicas) if isinstance(replicas, int) else 1,
            evidence_ids=intent.evidence_ids,
            changed_files={path: after_content},
            raw_diff=raw_diff,
        )

    def _mutate(
        self,
        intent: ChangeIntent,
        profile: GitOpsApplicationProfile,
        deployment: dict[str, Any],
    ) -> SemanticMutation:
        spec = deployment.get("spec")
        if not isinstance(spec, dict):
            raise ChangePlanningError("Deployment spec is required")
        if intent.change_type is ChangeType.SCALE_REPLICAS:
            before = spec.get("replicas", 1)
            if not isinstance(before, int) or intent.requested_replicas is None:
                raise ChangePlanningError("Deployment replicas could not be resolved")
            spec["replicas"] = intent.requested_replicas
            return SemanticMutation(
                resource_ref=intent.target_ref,
                mutation_type=intent.change_type,
                field="spec.replicas",
                before=before,
                after=intent.requested_replicas,
            )
        pod_spec = spec.get("template", {}).get("spec", {})
        containers = pod_spec.get("containers") if isinstance(pod_spec, dict) else None
        if not isinstance(containers, list) or len(containers) != 1:
            raise ChangePlanningError("Rollback target must have exactly one container")
        container = containers[0]
        if not isinstance(container, dict) or not isinstance(container.get("image"), str):
            raise ChangePlanningError("Deployment container image is required")
        target_image = profile.known_good_images.get(intent.target_ref)
        if target_image is None:
            raise ChangePlanningError("No operator-approved known-good digest is configured")
        before_image = container["image"]
        container["image"] = target_image
        return SemanticMutation(
            resource_ref=intent.target_ref,
            mutation_type=intent.change_type,
            field="spec.template.spec.containers[0].image",
            before=before_image,
            after=target_image,
            artifact_digest=target_image.rsplit("@", 1)[1],
        )
