from app.deployment.models import (
    AssessmentItem,
    DeploymentConfiguration,
    MigrationAssessment,
    ReadinessLevel,
)


def assess_migration(
    configuration: DeploymentConfiguration, profile_id: str
) -> MigrationAssessment:
    target = next(
        (item for item in configuration.targets if item.profile_id == profile_id), None
    )
    if target is None:
        raise ValueError("Unknown deployment target profile")
    observation = next(
        (
            item
            for item in configuration.observability
            if item.id == target.observability_profile_ref
        ),
        None,
    )
    health_ready = bool(observation.health if observation else True)
    metrics_ready = bool(observation.metrics if observation else False)
    logs_ready = bool(observation.logs if observation else False)
    ticket_ready = target.ticket_profile_ref is not None and bool(
        observation.tickets if observation else True
    )
    items = (
        AssessmentItem(capability="SSH", status="READY"),
        AssessmentItem(capability="Service Control", status="READY"),
        AssessmentItem(capability="Health", status="READY" if health_ready else "MISSING"),
        AssessmentItem(capability="Metrics", status="READY" if metrics_ready else "OPTIONAL"),
        AssessmentItem(capability="Logs", status="READY" if logs_ready else "OPTIONAL"),
        AssessmentItem(
            capability="Ticket Adapter", status="READY" if ticket_ready else "MISSING"
        ),
        AssessmentItem(capability="Approval", status="READY"),
        AssessmentItem(capability="Execution", status="READY"),
        AssessmentItem(capability="Verification", status="READY"),
    )
    levels: set[ReadinessLevel] = set()
    if health_ready or metrics_ready:
        levels.add(ReadinessLevel.OBSERVE_READY)
    if ReadinessLevel.OBSERVE_READY in levels:
        levels.add(ReadinessLevel.REMEDIATION_READY)
    if health_ready and metrics_ready and logs_ready and ticket_ready:
        levels.add(ReadinessLevel.FULL_INCIDENT_READY)
    result = (
        "FULL INCIDENT PATH READY"
        if ReadinessLevel.FULL_INCIDENT_READY in levels
        else "MINIMAL REMEDIATION PATH READY"
        if ReadinessLevel.REMEDIATION_READY in levels
        else "OBSERVATION CONFIGURATION REQUIRED"
    )
    return MigrationAssessment(
        profile_id=profile_id,
        items=items,
        readiness_levels=frozenset(levels),
        result=result,
    )
