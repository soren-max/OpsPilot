# Remediation vs Change

REMEDIATE restores service through a bounded operational action and an operator-selected executor.
CHANGE edits desired state through Git. A restart may be remediation; an image rollback or replica
change is a versioned configuration change. Sharing policy/HITL does not make their side effects the
same, so OpsPilot gives them separate ports, records, lifecycle states, and UI.
