import pytest

from app.domain.incidents.lifecycle import (
    TRANSITIONS,
    InvalidIncidentTransition,
    require_transition,
)
from app.domain.incidents.models import IncidentStatus


@pytest.mark.parametrize(
    ("current", "target"),
    [(current, target) for current, targets in TRANSITIONS.items() for target in targets],
)
def test_allowed_incident_transitions(current: IncidentStatus, target: IncidentStatus) -> None:
    require_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (current, target)
        for current in IncidentStatus
        for target in IncidentStatus
        if target not in TRANSITIONS[current]
    ],
)
def test_unlisted_incident_transitions_fail_closed(
    current: IncidentStatus, target: IncidentStatus
) -> None:
    with pytest.raises(InvalidIncidentTransition):
        require_transition(current, target)
