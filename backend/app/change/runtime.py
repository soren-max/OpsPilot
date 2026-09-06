from app.adapters.git import GitHubGitChangeProvider
from app.core.config import Settings
from app.domain.change import GitChangeProvider, GitOpsApplicationProfile


def build_git_provider(settings: Settings, profile: GitOpsApplicationProfile) -> GitChangeProvider:
    if settings.gitops_provider != "github" or settings.github_token is None:
        raise ValueError("GitOps change execution is not operator-configured")
    if settings.github_repository != profile.repository_ref:
        raise ValueError("Stored profile repository does not match operator configuration")
    if settings.github_base_branch != profile.base_branch:
        raise ValueError("Stored profile branch does not match operator configuration")
    return GitHubGitChangeProvider(
        repository=settings.github_repository,
        base_branch=settings.github_base_branch,
        token=settings.github_token.get_secret_value(),
        allowed_paths=frozenset({profile.manifest_root}),
    )


def load_profiles(settings: Settings) -> tuple[GitOpsApplicationProfile, ...]:
    import json
    from pathlib import Path

    import yaml  # type: ignore[import-untyped]

    if not settings.gitops_profiles_path:
        raise ValueError("Operator GitOps profiles are not configured")
    raw = yaml.safe_load(Path(settings.gitops_profiles_path).read_text())
    if not isinstance(raw, list):
        raise ValueError("GitOps configuration must be a list of operator profiles")
    profiles = tuple(GitOpsApplicationProfile.model_validate_json(json.dumps(item)) for item in raw)
    scopes = [(p.service, p.environment) for p in profiles]
    if len(scopes) != len(set(scopes)):
        raise ValueError("GitOps profile scope is ambiguous")
    return profiles


def resolve_profile(settings: Settings, service: str, environment: str) -> GitOpsApplicationProfile:
    matches = [
        p for p in load_profiles(settings) if (p.service, p.environment) == (service, environment)
    ]
    if len(matches) != 1:
        raise ValueError("No unique operator profile for service/environment")
    return matches[0]
