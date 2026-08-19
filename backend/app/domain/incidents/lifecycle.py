from app.domain.incidents.models import IncidentStatus


class InvalidIncidentTransition(ValueError):
    pass


TRANSITIONS: dict[IncidentStatus, frozenset[IncidentStatus]] = {
    IncidentStatus.OPEN: frozenset({IncidentStatus.INVESTIGATING, IncidentStatus.FAILED}),
    IncidentStatus.INVESTIGATING: frozenset(
        {IncidentStatus.MITIGATING, IncidentStatus.RESOLVED, IncidentStatus.FAILED}
    ),
    IncidentStatus.MITIGATING: frozenset({IncidentStatus.VERIFYING, IncidentStatus.FAILED}),
    IncidentStatus.VERIFYING: frozenset(
        {IncidentStatus.MITIGATING, IncidentStatus.RESOLVED, IncidentStatus.FAILED}
    ),
    IncidentStatus.RESOLVED: frozenset({IncidentStatus.CLOSED}),
    IncidentStatus.CLOSED: frozenset(),
    IncidentStatus.FAILED: frozenset({IncidentStatus.INVESTIGATING}),
}


def require_transition(current: IncidentStatus, target: IncidentStatus) -> None:
    if target not in TRANSITIONS.get(current, frozenset()):
        raise InvalidIncidentTransition(f"Illegal incident transition: {current} -> {target}")
