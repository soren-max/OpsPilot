from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx

from app.domain.change import GitOpsStatus


@dataclass(frozen=True)
class ArgoCDGitOpsReconciler:
    base_url: str
    token: str = field(repr=False)
    allowed_applications: frozenset[str]

    async def get_application_status(self, application_ref: str) -> GitOpsStatus:
        self._require_allowed(application_ref)
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=10,
        ) as client:
            response = await client.get(f"/api/v1/applications/{quote(application_ref, safe='')}")
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
        if payload.get("metadata", {}).get("name") != application_ref:
            raise ValueError("Argo application response identity mismatch")
        status = payload.get("status", {})
        sync = status.get("sync", {}) if isinstance(status, dict) else {}
        health = status.get("health", {}) if isinstance(status, dict) else {}
        resources = status.get("resources", []) if isinstance(status, dict) else []
        if (
            not isinstance(sync, dict)
            or not isinstance(health, dict)
            or not isinstance(resources, list)
        ):
            raise ValueError("Argo status shape is invalid")
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
                f"/api/v1/applications/{quote(application_ref, safe='')}",
                params={"refresh": "normal"},
            )
            response.raise_for_status()

    def _require_allowed(self, application_ref: str) -> None:
        if application_ref not in self.allowed_applications:
            raise ValueError("Argo CD application is outside the operator allowlist")
