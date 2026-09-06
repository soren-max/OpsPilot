from dataclasses import dataclass

from app.domain.change import GitOpsStatus


@dataclass
class FakeGitOpsReconciler:
    status: GitOpsStatus

    async def get_application_status(self, application_ref: str) -> GitOpsStatus:
        if application_ref != self.status.application_ref:
            raise ValueError("Unknown application")
        return self.status

    async def refresh(self, application_ref: str) -> None:
        if application_ref != self.status.application_ref:
            raise ValueError("Unknown application")
