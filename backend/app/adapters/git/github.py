from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx

from app.domain.change import PullRequest, PullRequestState, ReviewState

GITHUB_API_VERSION = "2026-03-10"


@dataclass(frozen=True)
class GitHubGitChangeProvider:
    """Operator-configured, repository-bound GitHub REST adapter."""

    repository: str
    base_branch: str
    token: str = field(repr=False)
    allowed_paths: frozenset[str] = frozenset()
    api_base: str = "https://api.github.com"

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repository):
            raise ValueError("Invalid operator repository")
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*", self.base_branch)
            or ".." in self.base_branch
        ):
            raise ValueError("Invalid operator base branch")

    def _path(self, path: str) -> str:
        if path not in self.allowed_paths or any(p in {"", ".", ".."} for p in path.split("/")):
            raise ValueError("Git path is outside the operator allowlist")
        return quote(path, safe="/")

    @staticmethod
    def _branch(branch: str) -> str:
        if not re.fullmatch(r"opspilot/change/[a-f0-9-]{36}", branch):
            raise ValueError("Invalid deterministic change branch")
        return branch

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
            "GET", f"/repos/{self.repository}/contents/{self._path(path)}", params={"ref": revision}
        )
        if (
            data.get("type") != "file"
            or data.get("encoding") != "base64"
            or data.get("size", 0) > 250_000
        ):
            raise ValueError("Git manifest must be a bounded regular file")
        return base64.b64decode(str(data["content"])).decode()

    async def create_branch(self, branch: str, source_revision: str) -> None:
        self._branch(branch)
        await self._request(
            "POST",
            f"/repos/{self.repository}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": source_revision},
        )

    async def commit_changes(self, branch: str, files: dict[str, str], message: str) -> str:
        self._branch(branch)
        revision = self.branches_not_supported_message(files)
        for path, content in files.items():
            current = await self._request(
                "GET",
                f"/repos/{self.repository}/contents/{self._path(path)}",
                params={"ref": branch},
            )
            committed = await self._request(
                "PUT",
                f"/repos/{self.repository}/contents/{self._path(path)}",
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
        self._branch(branch)
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
            params={
                "state": "all",
                "head": f"{owner}:{branch}",
                "base": self.base_branch,
                "per_page": 100,
            },
        )
        matches = [
            item
            for item in items
            if f"OpsPilot Change ID: {change_id}" in str(item.get("body", "")).splitlines()
            and item.get("base", {}).get("ref") == self.base_branch
            and item.get("head", {}).get("repo", {}).get("full_name") == self.repository
        ]
        if len(matches) > 1:
            raise ValueError("Ambiguous PR correlation")
        return await self.get_pull_request(str(matches[0]["number"])) if matches else None

    async def get_pull_request(self, pull_request_id: str) -> PullRequest:
        data = await self._request("GET", f"/repos/{self.repository}/pulls/{pull_request_id}")
        if (
            data.get("base", {}).get("ref") != self.base_branch
            or data.get("base", {}).get("repo", {}).get("full_name") != self.repository
            or data.get("head", {}).get("repo", {}).get("full_name") != self.repository
        ):
            raise ValueError("PR repository/base correlation mismatch")
        return self._pull_request(data, await self.get_review_state(pull_request_id))

    async def get_review_state(self, pull_request_id: str) -> ReviewState:
        pull = await self._request("GET", f"/repos/{self.repository}/pulls/{pull_request_id}")
        reviews: list[dict[str, Any]] = []
        for page in range(1, 11):
            batch = await self._request(
                "GET",
                f"/repos/{self.repository}/pulls/{pull_request_id}/reviews",
                params={"per_page": 100, "page": page},
            )
            reviews.extend(batch)
            if len(batch) < 100:
                break
        else:
            return ReviewState.WAITING  # bounded observation cannot prove complete review state
        latest_by_reviewer: dict[str, str] = {}
        for item in reviews:
            reviewer = item.get("user", {}).get("login")
            state = str(item.get("state", "")).upper()
            if reviewer == pull.get("user", {}).get("login"):
                continue
            if state == "APPROVED" and item.get("commit_id") != pull["head"]["sha"]:
                state = "DISMISSED"
            if isinstance(reviewer, str) and state in {
                "APPROVED",
                "CHANGES_REQUESTED",
                "DISMISSED",
            }:
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
