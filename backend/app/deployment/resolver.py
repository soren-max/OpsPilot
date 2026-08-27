from dataclasses import dataclass

from app.application.deployment import DeploymentTargetProfile
from app.deployment.models import DeploymentConfiguration
from app.domain.actions.models import TargetEnvironment


@dataclass(frozen=True)
class ConfigDeploymentEnvironmentResolver:
    configuration: DeploymentConfiguration

    def resolve(
        self,
        *,
        service: str,
        environment: TargetEnvironment,
        target_ref: str,
    ) -> DeploymentTargetProfile:
        matches = [
            profile
            for profile in self.configuration.targets
            if profile.service == service
            and profile.environment is environment
            and profile.target_ref == target_ref
        ]
        if len(matches) != 1:
            raise ValueError("No unique approved deployment target profile exists")
        return matches[0]
