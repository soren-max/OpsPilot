# ADR 0017: Git Side Effects Use Outbox and Reconciliation

Status: Accepted

An approved `ChangeRecord` and its outbox intent commit atomically. Dispatch uses a lease and stable
change/branch/correlation identity. An indeterminate Git result becomes `UNKNOWN`; OpsPilot searches
for the existing PR instead of retrying. Unprovable or mismatched revisions require reconciliation.
