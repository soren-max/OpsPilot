from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from app.domain.change import PullRequest, PullRequestState, ReviewState


@dataclass
class FakeGitChangeProvider:
    """Deterministic offline Git/PR lifecycle used by CI and the synthetic lab."""

    base_revision: str = "a" * 40
    base_files: dict[str, str] = field(default_factory=dict)
    branches: dict[str, str] = field(default_factory=dict)
    branch_files: dict[str, dict[str, str]] = field(default_factory=dict)
    pull_requests: dict[str, PullRequest] = field(default_factory=dict)
    correlations: dict[str, str] = field(default_factory=dict)
    create_pr_timeout_after_accept: bool = False

    async def read_base_revision(self) -> str:
        return self.base_revision

    async def read_file(self, path: str, revision: str) -> str:
        if revision != self.base_revision:
            for branch, branch_revision in self.branches.items():
                if branch_revision == revision:
                    return self.branch_files[branch][path]
        if revision != self.base_revision:
            raise ValueError("Unknown immutable revision")
        return self.base_files[path]

    async def create_branch(self, branch: str, source_revision: str) -> None:
        existing = self.branches.get(branch)
        if existing is not None and existing != source_revision:
            raise ValueError("Branch correlation conflict")
        self.branches[branch] = source_revision
        self.branch_files[branch] = dict(self.base_files)

    async def commit_changes(self, branch: str, files: dict[str, str], message: str) -> str:
        if branch not in self.branches:
            raise ValueError("Branch does not exist")
        self.branch_files[branch].update(files)
        payload = branch + message + "".join(f"{k}:{v}" for k, v in sorted(files.items()))
        revision = hashlib.sha1(payload.encode(), usedforsecurity=False).hexdigest()
        self.branches[branch] = revision
        return revision

    async def create_pull_request(self, branch: str, title: str, body: str) -> PullRequest:
        del title
        change_id = _correlation(body)
        existing = await self.find_pull_request(branch, change_id)
        if existing is not None:
            return existing
        number = str(len(self.pull_requests) + 1)
        item = PullRequest(
            pull_request_id=number,
            url=f"https://gitops.local/pull/{number}",
            branch=branch,
            head_revision=self.branches[branch],
            state=PullRequestState.OPEN,
            review_state=ReviewState.WAITING,
        )
        self.pull_requests[number] = item
        self.correlations[number] = change_id
        if self.create_pr_timeout_after_accept:
            raise TimeoutError("PR creation outcome indeterminate")
        return item

    async def find_pull_request(self, branch: str, change_id: str) -> PullRequest | None:
        return next(
            (
                item
                for key, item in self.pull_requests.items()
                if item.branch == branch and self.correlations.get(key) == change_id
            ),
            None,
        )

    async def get_pull_request(self, pull_request_id: str) -> PullRequest:
        return self.pull_requests[pull_request_id]

    async def get_review_state(self, pull_request_id: str) -> ReviewState:
        return self.pull_requests[pull_request_id].review_state

    async def resolve_revision(self, revision: str) -> str:
        return revision

    # Lab-only controls model a separate external human/Git boundary. Application
    # services only receive this object through the narrower GitChangeProvider port.
    def external_review(self, pull_request_id: str, *, approved: bool) -> None:
        item = self.pull_requests[pull_request_id]
        self.pull_requests[pull_request_id] = item.model_copy(
            update={
                "review_state": (
                    ReviewState.APPROVED if approved else ReviewState.CHANGES_REQUESTED
                )
            }
        )

    def external_merge(self, pull_request_id: str) -> str:
        item = self.pull_requests[pull_request_id]
        if item.review_state is not ReviewState.APPROVED:
            raise ValueError("External review approval is required")
        self.base_revision = item.head_revision
        self.base_files = dict(self.branch_files[item.branch])
        self.pull_requests[pull_request_id] = item.model_copy(
            update={
                "state": PullRequestState.MERGED,
                "merged_revision": item.head_revision,
            }
        )
        return item.head_revision


def _correlation(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("OpsPilot Change ID: "):
            return line.removeprefix("OpsPilot Change ID: ").strip()
    raise ValueError("PR body lacks OpsPilot Change ID")
