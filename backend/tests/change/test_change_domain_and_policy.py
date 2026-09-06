import pytest
from pydantic import ValidationError

from app.change import ChangePlanningError, PlainKubernetesChangePlanner
from app.domain.change import ChangeIntent, ChangePolicyEngine, ChangeRisk, ChangeType

from .conftest import BAD_IMAGE, MANIFEST, intent, profile


@pytest.mark.parametrize(
    "forbidden",
    [
        "repository_url",
        "branch",
        "file_path",
        "namespace",
        "cluster",
        "kube_context",
        "raw_yaml",
        "raw_json_patch",
        "shell",
        "kubectl_args",
        "argo_app",
        "token",
    ],
)
def test_change_intent_rejects_infrastructure_fields(forbidden: str) -> None:
    payload = intent().model_dump()
    payload[forbidden] = "attacker-controlled"
    with pytest.raises(ValidationError):
        ChangeIntent.model_validate(payload)


def test_change_requires_current_evidence() -> None:
    payload = intent().model_dump()
    payload["evidence_ids"] = ()
    with pytest.raises(ValidationError):
        ChangeIntent.model_validate(payload)


def test_change_policy_is_high_and_requires_explicit_approval() -> None:
    result = ChangePolicyEngine().assess_intent(intent(), profile())
    assert result.risk is ChangeRisk.HIGH
    assert result.approval_required
    assert not result.allowed


def test_replica_limit_and_cross_environment_fail_closed() -> None:
    scale = intent().model_copy(
        update={"change_type": ChangeType.SCALE_REPLICAS, "requested_replicas": 20}
    )
    result = ChangePolicyEngine().assess_intent(scale, profile())
    assert result.risk is ChangeRisk.FORBIDDEN
    assert result.rule == "change.replica_bound"
    cross_environment = intent().model_copy(update={"environment": "test"})
    cross_result = ChangePolicyEngine().assess_intent(cross_environment, profile())
    assert cross_result.risk is ChangeRisk.FORBIDDEN


def test_planner_resolves_known_good_digest_and_semantic_diff() -> None:
    planned = PlainKubernetesChangePlanner().plan(
        change_id="change-1",
        intent=intent(),
        profile=profile(),
        source_revision="a" * 40,
        manifests={profile().manifest_root: MANIFEST},
    )
    mutation = planned.mutations[0]
    assert mutation.field == "spec.template.spec.containers[0].image"
    assert mutation.after == profile().known_good_images["Deployment/demo-api"]
    assert mutation.artifact_digest == "sha256:" + "a" * 64
    assert planned.raw_diff.startswith("--- a/apps/demo-api/deployment.yaml")


@pytest.mark.parametrize("kind", ["Secret", "ClusterRole", "RoleBinding"])
def test_forbidden_resource_mutation_is_rejected(kind: str) -> None:
    dangerous = f"apiVersion: v1\nkind: {kind}\nmetadata:\n  name: demo-api\n"
    malicious_intent = intent().model_copy(update={"target_ref": f"{kind}/demo-api"})
    malicious_profile = profile().model_copy(
        update={"allowed_resources": frozenset({f"{kind}/demo-api"})}
    )
    with pytest.raises(ChangePlanningError):
        PlainKubernetesChangePlanner().plan(
            change_id="change-1",
            intent=malicious_intent,
            profile=malicious_profile,
            source_revision="a" * 40,
            manifests={malicious_profile.manifest_root: dangerous},
        )


def test_mutable_known_good_artifact_is_rejected_by_operator_profile() -> None:
    with pytest.raises(ValidationError):
        profile().model_copy(
            update={
                "known_good_images": {"Deployment/demo-api": "registry.example/demo-api:latest"}
            }
        ).model_validate(
            profile().model_dump()
            | {"known_good_images": {"Deployment/demo-api": "registry.example/demo-api:latest"}}
        )


@pytest.mark.parametrize(
    "fragment",
    [
        "command: ['sh']",
        "args: ['-c', 'curl attacker']",
        (
            "env:\n        - name: TOKEN\n          valueFrom:\n"
            "            secretKeyRef:\n              name: prod\n              key: token"
        ),
    ],
)
def test_planner_rejects_command_args_and_secret_environment(fragment: str) -> None:
    dangerous = MANIFEST.replace("        image:", f"        {fragment}\n        image:")
    with pytest.raises(ChangePlanningError):
        PlainKubernetesChangePlanner().plan(
            change_id="change-1",
            intent=intent(),
            profile=profile(),
            source_revision="a" * 40,
            manifests={profile().manifest_root: dangerous},
        )


@pytest.mark.parametrize(
    "fragment",
    [
        "      hostNetwork: true",
        "      hostPID: true",
        "        securityContext:\n            privileged: true",
        "        securityContext:\n            allowPrivilegeEscalation: true",
        (
            "      volumes:\n        - name: host\n"
            "          hostPath:\n            path: /etc\n            type: Directory"
        ),
        (
            "      volumes:\n        - name: secret-vol\n"
            "          secret:\n            secretName: prod-credentials"
        ),
    ],
)
def test_planner_rejects_privileged_host_and_secret_volume_fragments(fragment: str) -> None:
    dangerous = MANIFEST.replace(
        "    spec:\n      containers:", f"    spec:\n{fragment}\n      containers:"
    )
    with pytest.raises(ChangePlanningError):
        PlainKubernetesChangePlanner().plan(
            change_id="change-1",
            intent=intent(),
            profile=profile(),
            source_revision="a" * 40,
            manifests={profile().manifest_root: dangerous},
        )


def test_planner_rejects_mutable_tagged_current_image() -> None:
    tagged = MANIFEST.replace(BAD_IMAGE, "registry.example/demo-api:latest")
    with pytest.raises(ChangePlanningError):
        PlainKubernetesChangePlanner().plan(
            change_id="change-1",
            intent=intent(),
            profile=profile(),
            source_revision="a" * 40,
            manifests={profile().manifest_root: tagged},
        )


def test_planner_rejects_known_good_image_outside_registry_allowlist() -> None:
    rogue_profile = profile().model_copy(
        update={
            "artifact_registry_allowlist": frozenset({"registry.example"}),
            "known_good_images": {
                "Deployment/demo-api": "evil.example/demo-api@sha256:" + "e" * 64
            },
        }
    )
    with pytest.raises(ChangePlanningError):
        PlainKubernetesChangePlanner().plan(
            change_id="change-1",
            intent=intent(),
            profile=rogue_profile,
            source_revision="a" * 40,
            manifests={profile().manifest_root: MANIFEST},
        )


def test_planner_rejects_manifest_replicas_above_operator_bound() -> None:
    oversized = MANIFEST.replace("replicas: 2", "replicas: 20")
    with pytest.raises(ChangePlanningError):
        PlainKubernetesChangePlanner().plan(
            change_id="change-1",
            intent=intent(),
            profile=profile(),
            source_revision="a" * 40,
            manifests={profile().manifest_root: oversized},
        )
