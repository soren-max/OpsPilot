# 19 — RAG Incident Memory

## Why not put every log in a vector database?

Raw logs are high-volume, repetitive, secret-prone, and lack a stable incident outcome. OpsPilot
indexes a reviewed projection only after an incident is resolved or closed and diagnosed. This
gives every memory a source incident, root cause, remediation, and verification result.

## Is memory evidence?

No. It is historical context. Current Evidence IDs still ground the diagnosis and any action.
