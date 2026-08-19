# Contributing to OpsPilot

Thank you for helping build safer incident-response automation.

1. Start from an up-to-date `main` branch.
2. Create a focused branch such as `feat/action-name` or `fix/policy-rule`.
3. Use Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `ci:`,
   `chore:`, or `build:`).
4. Add or update tests for every policy and execution-path change.
5. Run all checks documented in `docs/development.md`.
6. Open a pull request and complete the security-impact section.

Pull requests that add arbitrary command execution, bypass policy, expose credentials, or mix
unrelated refactors will not be accepted. Do not include employer, customer, internal network,
or production data in issues, fixtures, logs, or commits.
