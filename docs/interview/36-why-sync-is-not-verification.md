# Why Sync Is Not Verification

Synced means Argo's observed Git revision matches desired state. Healthy means its Kubernetes health
assessment passes. Neither proves the incident symptom recovered. OpsPilot separately queries current
health, metrics, and logs. A Healthy app with a high error rate leaves the Incident unresolved.
