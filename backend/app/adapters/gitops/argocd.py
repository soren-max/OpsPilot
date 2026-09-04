from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.domain.change import GitOpsStatus


@dataclass(frozen=True)
class ArgoCDGitOpsReconciler:
    base_url: str
    token: str
    allowed_applications: frozenset[str]

    async def get_application_status(self, application_ref: str) -> GitOpsStatus:
        self._require_allowed(application_ref)
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=10,
        ) as client:
            response = await client.get(f"/api/v1/applications/{application_ref}")
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
        status = payload.get("status", {})
        sync = status.get("sync", {}) if isinstance(status, dict) else {}
        health = status.get("health", {}) if isinstance(status, dict) else {}
        resources = status.get("resources", []) if isinstance(status, dict) else []
        return GitOpsStatus(
            application_ref=application_ref,
            revision=sync.get("revision") if isinstance(sync, dict) else None,
            sync_status=str(sync.get("status", "Unknown")),
            health_status=str(health.get("status", "Unknown")),
            resources=tuple(
                f"{item.get('kind', 'Unknown')}/{item.get('name', 'Unknown')}"
                for item in resources
                if isinstance(item, dict)
            ),
        )

    async def refresh(self, application_ref: str) -> None:
        self._require_allowed(application_ref)
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=10,
        ) as client:
            response = await client.get(
                f"/api/v1/applications/{application_ref}", params={"refresh": "normal"}
            )
            response.raise_for_status()

    def _require_allowed(self, application_ref: str) -> None:
        if application_ref not in self.allowed_applications:
            raise ValueError("Argo CD application is outside the operator allowlist")
