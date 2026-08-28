import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.adapters.execution.harness import HarnessPipelineExecutionBackend, HttpxHarnessClient
from app.adapters.execution.legacy import ActionExecutorBackend
from app.application.action_service import ActionService
from app.core.config import Settings
from app.deployment import ConfigDeploymentEnvironmentResolver, load_deployment_configuration
from app.domain.actions.models import ActionRequest, ActionType, TargetEnvironment
from app.domain.execution import BackendType, ExecutionBackend, ExecutionProfile
from app.execution.router import ExecutionRouter
from app.execution.service import ExecutionDispatcher, ExecutionPlaneService, ExecutionVerifier
from app.repositories.execution_models import ExecutionRecord


class ActionExecutorVerifier(ExecutionVerifier):
    def __init__(self, action_service: ActionService) -> None:
        self.action_service = action_service

    async def verify(self, execution: ExecutionRecord) -> bool:
        request = ActionRequest.model_validate_json(json.dumps(execution.request_payload))
        result = await self.action_service.executor.verify(request)
        return result.verified


def build_execution_plane(
    db: Session, settings: Settings, action_service: ActionService
) -> tuple[ExecutionPlaneService, ExecutionDispatcher]:
    native_type = (
        BackendType.ANSIBLE if settings.selected_executor == "ansible" else BackendType.MOCK
    )
    native = ActionExecutorBackend(action_service.executor, native_type)
    profiles: list[ExecutionProfile] = []
    routes: dict[tuple[str, str], str] = {}
    backends: dict[str, ExecutionBackend] = {native_type.value: native}
    descriptors = [native.descriptor]
    deployment_resolver = None
    if settings.deployment_config_path:
        configuration = load_deployment_configuration(Path(settings.deployment_config_path))
        deployment_resolver = ConfigDeploymentEnvironmentResolver(configuration)
        for target in configuration.targets:
            profile = ExecutionProfile(
                name=target.profile_id,
                backend_type=BackendType.ANSIBLE,
                environment=target.environment,
                allowed_action_types=target.allowed_actions,
                target_mapping={target.target_ref: target.service},
                immutable_refs={
                    "deployment_target_profile": target.profile_id,
                    "connection_profile": target.connection_profile_ref,
                    "service_control_profile": target.service_control_profile_ref,
                    "verification_profile": target.health_profile_ref,
                },
            )
            profiles.append(profile)
        backends[BackendType.ANSIBLE.value] = native
    else:
        for environment in TargetEnvironment:
            profile = ExecutionProfile(
                name=f"{environment.value}-restart-{native_type.value}",
                backend_type=native_type,
                environment=environment,
                allowed_action_types=frozenset({ActionType.RESTART_SERVICE}),
            )
            profiles.append(profile)
            routes[(ActionType.RESTART_SERVICE.value, environment.value)] = profile.name
    if settings.harness_restart_pipeline_identifier:
        assert settings.harness_base_url
        assert settings.harness_api_key
        assert settings.harness_account_id
        assert settings.harness_org_id
        assert settings.harness_project_id
        harness = HarnessPipelineExecutionBackend(
            HttpxHarnessClient(
                settings.harness_base_url,
                settings.harness_api_key.get_secret_value(),
                timeout_seconds=settings.execution_timeout_seconds,
            ),
            account_id=settings.harness_account_id,
            org_id=settings.harness_org_id,
            project_id=settings.harness_project_id,
        )
        profile = ExecutionProfile(
            name="production-restart-harness",
            backend_type=BackendType.HARNESS,
            environment=TargetEnvironment.PRODUCTION,
            allowed_action_types=frozenset({ActionType.RESTART_SERVICE}),
            target_mapping={target: target for target in action_service.policy.allowed_targets},
            immutable_refs={
                "pipeline_identifier": settings.harness_restart_pipeline_identifier
            },
        )
        profiles.append(profile)
        routes[
            (ActionType.RESTART_SERVICE.value, TargetEnvironment.PRODUCTION.value)
        ] = profile.name
        backends[BackendType.HARNESS.value] = harness
        descriptors.append(harness.descriptor)
    router = ExecutionRouter(
        tuple(profiles),
        tuple(descriptors),
        routes,
        deployment_resolver=deployment_resolver,
    )
    return (
        ExecutionPlaneService(db, router),
        ExecutionDispatcher(
            db,
            profiles=tuple(profiles),
            backends=backends,
            verifier=ActionExecutorVerifier(action_service),
            lease_seconds=settings.execution_dispatch_lease_seconds,
        ),
    )
