from pathlib import Path

import pytest

from app import lab

ROOT = Path(__file__).resolve().parents[3]


def test_normalized_demo_ids_are_stable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAB_NORMALIZE_OUTPUT", "1")
    assert lab._display_id("random-uuid", "incident-id") == "<incident-id>"


def test_minimal_profile_excludes_optional_demo_dependencies() -> None:
    compose = (ROOT / "lab/docker-compose.yml").read_text(encoding="utf-8")
    minimal = compose.split("lab-runner-minimal:", maxsplit=1)[1].split(
        "lab-runner-full:", maxsplit=1
    )[0]
    assert "OPSPILOT_MEMORY_BACKEND: disabled" in minimal
    assert "qdrant:" not in minimal
    assert "OPENAI_API_KEY" not in compose


def test_canonical_demo_uses_real_governed_boundaries() -> None:
    source = (ROOT / "backend/app/lab.py").read_text(encoding="utf-8")
    assert "ApprovalService(db).approve" in source
    assert "build_action_service(db, settings)" in source
    assert "IncidentStatus.RESOLVED" in source
    assert "[10/10] Verification passed" in source


def test_demo_make_targets_are_repeatable_and_safely_scoped() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "demo-local: demo-reset demo-doctor lab-up demo-doctor-live" in makefile
    assert "demo-reset:" in makefile
    assert "down -v --remove-orphans" in makefile
    assert "lab-runner-minimal" in makefile
    assert "scripts/demo_doctor.py" in makefile
    assert "scripts/demo_compose.sh minimal" in makefile


def test_committed_transcript_is_normalized_real_demo_output() -> None:
    transcript = (ROOT / "docs/demo/local-demo-transcript.txt").read_text(encoding="utf-8")
    assert transcript.startswith("[1/10] Lab ready\n")
    assert "[10/10] Verification passed" in transcript
    assert "Final State: RESOLVED" in transcript
    assert "<incident-id>" in transcript
    assert "Container " not in transcript
    assert "alembic" not in transcript
