import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.worker import build_investigator
from app.workflows.incident.investigator import DeterministicInvestigator


def test_default_investigator_mode_is_offline_and_deterministic() -> None:
    settings = Settings(_env_file=None)
    assert settings.llm_mode == "deterministic"
    assert isinstance(build_investigator(settings), DeterministicInvestigator)


def test_llm_mode_requires_operator_owned_provider_configuration() -> None:
    with pytest.raises(ValidationError, match="LLM mode requires"):
        Settings(_env_file=None, LLM_MODE="llm", LLM_PROVIDER="openai")


def test_incident_cannot_supply_endpoint_or_model_selection_fields() -> None:
    settings = Settings(
        _env_file=None,
        LLM_MODE="llm",
        LLM_PROVIDER="openai",
        LLM_MODEL="configured-model",
        LLM_API_KEY="placeholder-test-key",
    )
    investigator = build_investigator(settings)
    assert investigator.metadata.model == "configured-model"
