# Agent Evaluation

M3B introduces reusable `InvestigationEvalCase` fixtures and reports Evidence Precision, Evidence
Recall, Action Accuracy, Grounding Validity, Unsupported Action Rate, Insufficient-Evidence Accuracy,
and root-cause category match. The same cases can exercise deterministic logic, fake providers, and
optional real-model evaluation without making CI depend on an API key.

Safety cases are first-class evaluations rather than anecdotal demos. A high-quality narrative still
fails if it invents evidence, proposes an unsupported action, injects authorization, or forces an
action when evidence is insufficient.
