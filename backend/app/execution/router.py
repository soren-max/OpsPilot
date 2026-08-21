from dataclasses import dataclass

from app.domain.actions.models import ActionRequest, RiskAssessment, RiskLevel
from app.domain.execution import (
    ExecutionBackendDescriptor,
    ExecutionMode,
    ExecutionProfile,
    ExecutionRoute,
)

_RISK_ORDER = {
    RiskLevel.READ_ONLY: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.FORBIDDEN: 4,
}


@dataclass(frozen=True)
class ExecutionRouter:
    profiles: tuple[ExecutionProfile, ...]
    descriptors: tuple[ExecutionBackendDescriptor, ...]
    routes: dict[tuple[str, str], str]

    def route(self, request: ActionRequest, assessment: RiskAssessment) -> ExecutionRoute:
        if assessment.risk_level in {RiskLevel.READ_ONLY, RiskLevel.FORBIDDEN}:
            raise ValueError("Read-only or forbidden actions have no execution route")
        profile_name = self.routes.get((request.action_type.value, request.environment.value))
        if profile_name is None:
            raise ValueError("No operator-owned execution route is configured")
        profile = next((item for item in self.profiles if item.name == profile_name), None)
        if profile is None:
            raise ValueError("Configured execution profile does not exist")
        descriptor = next(
            (item for item in self.descriptors if item.backend_type is profile.backend_type), None
        )
        if descriptor is None:
            raise ValueError("Execution backend is not registered")
        if request.action_type not in profile.allowed_action_types:
            raise ValueError("Execution profile does not allow this action")
        if request.action_type not in descriptor.supported_action_types:
            raise ValueError("Backend descriptor does not support this action")
        if request.environment is not profile.environment:
            raise ValueError("Execution profile environment does not match the request")
        if request.environment not in descriptor.supported_environments:
            raise ValueError("Backend does not support this environment")
        if _RISK_ORDER[assessment.risk_level] > _RISK_ORDER[descriptor.max_risk_level]:
            raise ValueError("Backend risk capability is lower than the policy assessment")
        return ExecutionRoute(
            backend_type=profile.backend_type,
            profile_name=profile.name,
            mode=ExecutionMode.REMEDIATE,
        )
