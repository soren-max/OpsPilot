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


def test_mcp_runtime_tool_surface_has_no_git_authority() -> None:
    # Behavioral check over the actual capability surface: the MCP broker may only
    # expose the fixed allowlist, none of which selects a Git repo, branch, manifest
    # path, Argo application, or merges a pull request.
    from app.adapters.mcp.broker import McpCapabilityBroker

    assert McpCapabilityBroker.TOOL_ALLOWLIST == (
        "get_service_metrics",
        "search_service_logs",
        "search_incident_tickets",
        "get_service_health",
        "retrieve_historical_incidents",
        "request_remediation",
    )
    assert not any(
        marker in tool
        for tool in McpCapabilityBroker.TOOL_ALLOWLIST
        for marker in ("git", "branch", "merge", "manifest", "argo", "change")
    )


def test_llm_has_no_git_provider_capability() -> None:
    # The reasoning surface must stay proposal-only: no Git provider, profile,
    # planner, or provider-transport reference may be reachable from AI code.
    ai_sources = [
        *sorted((ROOT / "ai").rglob("*.py")),
        *sorted((ROOT / "workflows" / "incident").rglob("*.py")),
    ]
    ai = "\n".join(path.read_text() for path in ai_sources)
    assert "GitChangeProvider" not in ai
    assert "GitOpsApplicationProfile" not in ai
    assert "create_branch" not in ai
    assert "create_pull_request" not in ai
    assert "ChangePlanner" not in ai
    assert "PlainKubernetes" not in ai


def test_git_provider_cannot_authorize_policy() -> None:
    # Transport adapters observe and write desired state only; the deterministic
    # policy authority lives in the domain and must not be reachable from them.
    git_sources = [*sorted((ROOT / "adapters" / "git").rglob("*.py"))]
    git = "\n".join(path.read_text() for path in git_sources)
    assert "ChangePolicyEngine" not in git
    assert "assess_intent" not in git
    assert "assess_change_set" not in git
    assert "domain.change.policy" not in git


def test_argo_adapter_cannot_resolve_incident() -> None:
    # The Argo adapter is a read-only observation port: it cannot resolve an
    # Incident, approve a change, or reach the change service.
    gitops_sources = [*sorted((ROOT / "adapters" / "gitops").rglob("*.py"))]
    gitops = "\n".join(path.read_text() for path in gitops_sources)
    assert "incident" not in gitops.lower()
    assert "approve" not in gitops.lower()
    assert "resolve" not in gitops.lower()
    assert "ChangeService" not in gitops
    assert "resolve_incident" not in gitops.lower()


def test_verification_remains_independent_of_gitops_sync_and_health() -> None:
    # Change verification must query current capabilities (health/metrics/logs);
    # it must not consult ChangeRecord or GitOps status as evidence.
    verification = (ROOT / "change" / "verification.py").read_text()
    assert "ChangeRecord" not in verification
    assert "sync_status" not in verification
    assert "health_status" not in verification
    assert "ChangeWatcher" not in verification
