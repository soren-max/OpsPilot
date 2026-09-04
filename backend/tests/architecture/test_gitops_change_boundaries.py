from pathlib import Path

from app.domain.change.ports import GitChangeProvider

ROOT = Path(__file__).parents[2] / "app"


def test_domain_has_no_github_or_argo_imports() -> None:
    domain = "\n".join(path.read_text() for path in (ROOT / "domain" / "change").glob("*.py"))
    assert "httpx" not in domain
    assert "github" not in domain.lower()
    assert "argocd" not in domain.lower()


def test_git_provider_port_cannot_merge_or_approve() -> None:
    assert not hasattr(GitChangeProvider, "merge_pull_request")
    assert not hasattr(GitChangeProvider, "approve_pull_request")


def test_change_workflow_has_no_kubectl_or_execution_backend_dependency() -> None:
    source = "\n".join(path.read_text() for path in (ROOT / "change").glob("*.py"))
    assert "kubectl" not in source
    assert "ExecutionBackend" not in source


def test_mcp_has_no_git_repo_branch_or_merge_capability() -> None:
    source = "\n".join(path.read_text() for path in (ROOT / "adapters" / "mcp").glob("*.py"))
    assert "merge_pull_request" not in source
    assert "create_branch" not in source
    assert "repository_url" not in source
