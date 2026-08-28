from dataclasses import dataclass

from app.domain.actions.models import ActionRequest, ActionType, RiskAssessment, RiskLevel

READ_ONLY_ACTIONS = frozenset(
    {ActionType.GET_SERVICE_STATUS, ActionType.HEALTH_CHECK}
)
MUTATING_ACTIONS = frozenset(
    {ActionType.START_SERVICE, ActionType.STOP_SERVICE, ActionType.RESTART_SERVICE}
)


@dataclass(frozen=True)
class ActionPolicyEngine:
    """Deterministic authorization boundary; no LLM decision is accepted here."""

    allowed_targets: frozenset[str]

    def assess(
        self, action: ActionRequest, *, approval_granted: bool = False
    ) -> RiskAssessment:
        if action.target not in self.allowed_targets:
            return RiskAssessment(
                risk_level=RiskLevel.FORBIDDEN,
                reason="Target is outside the configured allowlist.",
                approval_required=False,
                policy_rule="target.allowlist",
                allowed=False,
            )
        if action.action_type in READ_ONLY_ACTIONS:
            return RiskAssessment(
                risk_level=RiskLevel.READ_ONLY,
                reason="The action collects evidence without changing target state.",
                approval_required=False,
                policy_rule="action.read_only",
                allowed=True,
            )
        if action.action_type in MUTATING_ACTIONS:
            return RiskAssessment(
                risk_level=RiskLevel.MEDIUM,
                reason="Changing service state modifies infrastructure.",
                approval_required=True,
                policy_rule="action.service_mutation",
                allowed=approval_granted,
            )
        return RiskAssessment(
            risk_level=RiskLevel.FORBIDDEN,
            reason="The action has no explicit policy rule.",
            approval_required=False,
            policy_rule="action.default_deny",
            allowed=False,
        )
