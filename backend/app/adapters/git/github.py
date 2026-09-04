from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import httpx

from app.domain.change import PullRequest, PullRequestState, ReviewState

GITHUB_API_VERSION = "2026-03-10"


@dataclass(frozen=True)
class GitHubGitChangeProvider:
    """Operator-configured, repository-bound GitHub REST adapter."""

    repository: str
    base_branch: str
    token: str
    api_base: str = "https://api.github.com"

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        async with httpx.AsyncClient(
            base_url=self.api_base, headers=self._headers(), timeout=15
        ) as client:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

    async def read_base_revision(self) -> str:
        data = await self._request(
            "GET", f"/repos/{self.repository}/git/ref/heads/{self.base_branch}"
        )
        return str(data["object"]["sha"])

    async def read_file(self, path: str, revision: str) -> str:
        data = await self._request(
            "GET", f"/repos/{self.repository}/contents/{path}", params={"ref": revision}
        )
        return base64.b64decode(str(data["content"])).decode()

    async def create_branch(self, branch: str, source_revision: str) -> None:
        await self._request(
            "POST",
            f"/repos/{self.repository}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": source_revision},
        )

    async def commit_changes(self, branch: str, files: dict[str, str], message: str) -> str:
        revision = self.branches_not_supported_message(files)
        for path, content in files.items():
            current = await self._request(
                "GET", f"/repos/{self.repository}/contents/{path}", params={"ref": branch}
            )
            committed = await self._request(
                "PUT",
                f"/repos/{self.repository}/contents/{path}",
                json={
                    "message": message,
                    "content": base64.b64encode(content.encode()).decode(),
                    "sha": current["sha"],
                    "branch": branch,
                },
            )
            revision = str(committed["commit"]["sha"])
        return revision

    @staticmethod
    def branches_not_supported_message(files: dict[str, str]) -> str:
        if len(files) != 1:
            raise ValueError("GitHub M9 adapter requires exactly one bounded manifest file")
        return ""

    async def create_pull_request(self, branch: str, title: str, body: str) -> PullRequest:
        data = await self._request(
            "POST",
            f"/repos/{self.repository}/pulls",
            json={"head": branch, "base": self.base_branch, "title": title, "body": body},
        )
        return self._pull_request(data, ReviewState.WAITING)

    async def find_pull_request(self, branch: str, change_id: str) -> PullRequest | None:
        owner = self.repository.split("/", 1)[0]
        items = await self._request(
            "GET",
            f"/repos/{self.repository}/pulls",
            params={"state": "all", "head": f"{owner}:{branch}"},
        )
        for item in items:
            if f"OpsPilot Change ID: {change_id}" in str(item.get("body", "")):
                return self._pull_request(item, await self.get_review_state(str(item["number"])))
        return None

    async def get_pull_request(self, pull_request_id: str) -> PullRequest:
        data = await self._request("GET", f"/repos/{self.repository}/pulls/{pull_request_id}")
        return self._pull_request(data, await self.get_review_state(pull_request_id))

    async def get_review_state(self, pull_request_id: str) -> ReviewState:
        reviews = await self._request(
            "GET", f"/repos/{self.repository}/pulls/{pull_request_id}/reviews"
        )
        latest_by_reviewer: dict[str, str] = {}
        for item in reviews:
            reviewer = item.get("user", {}).get("login")
            state = str(item.get("state", "")).upper()
            if isinstance(reviewer, str) and state in {"APPROVED", "CHANGES_REQUESTED"}:
                latest_by_reviewer[reviewer] = state
        states = latest_by_reviewer.values()
        if "CHANGES_REQUESTED" in states:
            return ReviewState.CHANGES_REQUESTED
        if "APPROVED" in states:
            return ReviewState.APPROVED
        return ReviewState.WAITING

    async def resolve_revision(self, revision: str) -> str:
        data = await self._request("GET", f"/repos/{self.repository}/commits/{revision}")
        return str(data["sha"])

    @staticmethod
    def _pull_request(data: dict[str, Any], review: ReviewState) -> PullRequest:
        merged = bool(data.get("merged")) or data.get("merged_at") is not None
        return PullRequest(
            pull_request_id=str(data["number"]),
            url=str(data["html_url"]),
            branch=str(data["head"]["ref"]),
            head_revision=str(data["head"]["sha"]),
            state=(
                PullRequestState.MERGED
                if merged
                else PullRequestState.OPEN
                if data["state"] == "open"
                else PullRequestState.CLOSED
            ),
            review_state=review,
            merged_revision=str(data["merge_commit_sha"]) if merged else None,
        )
