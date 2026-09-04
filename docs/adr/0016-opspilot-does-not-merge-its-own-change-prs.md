# ADR 0016: OpsPilot Does Not Merge Its Own Change PRs

Status: Accepted

OpsPilot approval authorizes PR creation. Git review and protected-branch merge are a second human
gate. The `GitChangeProvider` has no approve or merge operation, making self-merge unavailable by
architecture rather than convention. A separate synthetic reviewer owns these actions in the lab.
