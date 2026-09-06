import base64
import json

import httpx
import pytest

from app.adapters.git.github import GITHUB_API_VERSION, GitHubGitChangeProvider
from app.adapters.gitops.argocd import ArgoCDGitOpsReconciler
from app.domain.change import PullRequestState, ReviewState

BRANCH = "opspilot/change/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PATH = "apps/demo-api/deployment.yaml"
HEAD = "a" * 40


def pull() -> dict:
    return {
        "number": 1,
        "html_url": "https://github.com/synthetic/desired-state/pull/1",
        "state": "closed",
        "merged": True,
        "merge_commit_sha": "b" * 40,
        "head": {"ref": BRANCH, "sha": HEAD, "repo": {"full_name": "synthetic/desired-state"}},
        "base": {"ref": "main", "repo": {"full_name": "synthetic/desired-state"}},
        "user": {"login": "opspilot-bot"},
    }


def transport(monkeypatch: pytest.MonkeyPatch, handler: object) -> None:
    client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: client(transport=httpx.MockTransport(handler), **kw)
    )


def provider() -> GitHubGitChangeProvider:
    return GitHubGitChangeProvider(
        repository="synthetic/desired-state",
        base_branch="main",
        token="synthetic-token",
        allowed_paths=frozenset({PATH}),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "review_state,commit,expected",
    [
        ("APPROVED", HEAD, ReviewState.APPROVED),
        ("APPROVED", "c" * 40, ReviewState.WAITING),
        ("DISMISSED", HEAD, ReviewState.WAITING),
        ("CHANGES_REQUESTED", HEAD, ReviewState.CHANGES_REQUESTED),
    ],
)
async def test_github_correlates_latest_external_review(
    monkeypatch: pytest.MonkeyPatch, review_state: str, commit: str, expected: ReviewState
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.headers["X-GitHub-Api-Version"] == GITHUB_API_VERSION
        assert request.url.path.startswith("/repos/synthetic/desired-state/")
        if request.url.path.endswith("/reviews"):
            return httpx.Response(
                200,
                json=[
                    {"user": {"login": "opspilot-bot"}, "state": "APPROVED", "commit_id": HEAD},
                    {"user": {"login": "human"}, "state": "APPROVED", "commit_id": HEAD},
                    {"user": {"login": "human"}, "state": review_state, "commit_id": commit},
                ],
            )
        return httpx.Response(200, json=pull())

    transport(monkeypatch, handle)
    result = await provider().get_pull_request("1")
    assert result.review_state is expected
    assert result.state is PullRequestState.MERGED
    assert result.head_revision == HEAD
    assert result.merged_revision == "b" * 40


@pytest.mark.asyncio
async def test_github_rejects_wrong_repository_response(monkeypatch: pytest.MonkeyPatch) -> None:
    item = pull()
    item["base"]["repo"]["full_name"] = "attacker/desired-state"
    transport(monkeypatch, lambda request: httpx.Response(200, json=item))
    with pytest.raises(ValueError, match="correlation mismatch"):
        await provider().get_pull_request("1")


@pytest.mark.asyncio
async def test_github_writes_only_profile_path_and_change_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.host == "api.github.com"
        if request.method == "PUT":
            body = json.loads(request.content)
            assert body["branch"] == BRANCH
            assert base64.b64decode(body["content"]) == b"synthetic desired state"
            return httpx.Response(200, json={"commit": {"sha": HEAD}})
        if request.method == "GET":
            return httpx.Response(200, json={"sha": "blob"})
        return httpx.Response(201, json={"object": {"sha": HEAD}})

    transport(monkeypatch, handle)
    git = provider()
    with pytest.raises(ValueError):
        await git.create_branch("main", HEAD)
    with pytest.raises(ValueError):
        await git.commit_changes(BRANCH, {".github/workflows/pwn.yml": "bad"}, "change")
    assert not requests
    await git.create_branch(BRANCH, HEAD)
    assert await git.commit_changes(BRANCH, {PATH: "synthetic desired state"}, "change") == HEAD
    assert [r.method for r in requests] == ["POST", "GET", "PUT"]


@pytest.mark.asyncio
@pytest.mark.parametrize("response_name", ["demo-api", "wrong-app"])
async def test_argo_reads_revision_sync_health_and_checks_identity(
    monkeypatch: pytest.MonkeyPatch, response_name: str
) -> None:
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "GET"
        assert request.url.path == "/api/v1/applications/demo-api"
        return httpx.Response(
            200,
            json={
                "metadata": {"name": response_name},
                "status": {
                    "sync": {"revision": HEAD, "status": "Synced"},
                    "health": {"status": "Degraded"},
                    "resources": [{"kind": "Deployment", "name": "demo-api"}],
                },
            },
        )

    transport(monkeypatch, handle)
    adapter = ArgoCDGitOpsReconciler("https://argo.example", "synthetic", frozenset({"demo-api"}))
    with pytest.raises(ValueError, match="allowlist"):
        await adapter.get_application_status("other")
    assert not calls
    if response_name == "wrong-app":
        with pytest.raises(ValueError, match="identity mismatch"):
            await adapter.get_application_status("demo-api")
    else:
        status = await adapter.get_application_status("demo-api")
        assert status.revision == HEAD
        assert status.sync_status == "Synced"
        assert status.health_status == "Degraded"
