.PHONY: demo demo-local demo-full demo-doctor demo-doctor-live demo-reset demo-down demo-transcript lab-up lab-up-full lab-inject lab-status lab-reset lab-down lab-demo memory-index memory-eval mcp-demo mcp-eval execution-demo harness-demo deployment-preview deployment-doctor migration-assess legacy-demo legacy-reset legacy-down portfolio-benchmark portfolio-demo-repeatability portfolio-legacy-compatibility portfolio-check gitops-lab-up gitops-lab-status gitops-demo gitops-review gitops-merge gitops-lab-reset gitops-lab-down gitops-e2e

COMPOSE = docker compose -f lab/docker-compose.yml
DEMO_CORE = postgres dependency web-01 web-02 prometheus loki promtail
LAB_CLI_ENV = OPSPILOT_SECRET_KEY=lab-cli-only-secret-key-at-least-32-characters

demo:
	@uv run --project backend --no-sync python -m app.demo

demo-doctor:
	@python3 scripts/demo_doctor.py

demo-doctor-live:
	@python3 scripts/demo_doctor.py --live

demo-reset:
	@$(COMPOSE) --profile demo-minimal --profile demo-full down -v --remove-orphans >/dev/null 2>&1 || true
	@echo "Demo reset complete: containers, volumes, incidents, checkpoints, and faults removed."

demo-down:
	@$(COMPOSE) --profile demo-minimal --profile demo-full down -v --remove-orphans

lab-up:
	@scripts/demo_compose.sh minimal

lab-up-full:
	@scripts/demo_compose.sh full

demo-local: demo-reset demo-doctor lab-up demo-doctor-live
	@$(COMPOSE) --profile demo-minimal run --rm --no-deps lab-runner-minimal || (echo "Demo workflow failed. Run make demo-reset, then retry."; exit 1)

demo-full: demo-reset demo-doctor lab-up-full demo-doctor-live
	@$(COMPOSE) --profile demo-full run --rm --no-deps lab-runner-full || (echo "Full demo failed. Run make demo-reset, then retry."; exit 1)

demo-transcript: demo-reset demo-doctor lab-up demo-doctor-live
	@$(COMPOSE) --profile demo-minimal run --rm --no-deps -e LAB_NORMALIZE_OUTPUT=1 lab-runner-minimal | sed -n '/^\[1\/10\]/,$$p' | tee docs/demo/local-demo-transcript.txt

lab-inject:
	@$(LAB_CLI_ENV) uv run --project backend --no-sync python -m app.lab inject "$(SCENARIO)"

lab-status:
	@$(LAB_CLI_ENV) uv run --project backend --no-sync python -m app.lab status

lab-reset:
	@$(LAB_CLI_ENV) uv run --project backend --no-sync python -m app.lab reset

lab-down: demo-down

lab-demo: demo-full

memory-index:
	uv run --project backend --no-sync python -m app.memory.index

memory-eval:
	uv run --project backend --no-sync python -m app.memory.eval --json-output evals/incident-memory/results.json

mcp-eval:
	uv run --project backend --no-sync python -m app.mcp_eval

mcp-demo:
	uv run --project backend --no-sync pytest backend/tests/mcp/test_mcp_server.py backend/tests/mcp/test_mcp_transports.py -q
	$(MAKE) mcp-eval

execution-demo:
	uv run --project backend --no-sync python -m app.execution.demo
	uv run --project backend --no-sync pytest backend/tests/execution -q

harness-demo:
	@test -n "$$OPSPILOT_HARNESS_API_KEY" || (echo "Set opt-in Harness credentials first"; exit 1)
	uv run --project backend --no-sync python -m app.execution.harness_demo

deployment-preview:
	@uv run --project backend --no-sync python -m app.deployment.cli preview --profile "$(PROFILE)"

deployment-doctor:
	@uv run --project backend --no-sync python -m app.deployment.cli doctor --profile "$(PROFILE)"

migration-assess:
	@uv run --project backend --no-sync python -m app.deployment.cli assess --profile "$(PROFILE)"

legacy-reset:
	@docker compose -f lab/docker-compose.yml --profile legacy down -v --remove-orphans >/dev/null 2>&1 || true

legacy-demo: legacy-reset
	@docker compose -f lab/docker-compose.yml --profile legacy up --build --abort-on-container-exit --exit-code-from legacy-runner legacy-runner

legacy-down:
	@docker compose -f lab/docker-compose.yml --profile legacy down -v --remove-orphans

portfolio-benchmark:
	@uv run --project backend --no-sync python -m app.evaluation.portfolio

portfolio-demo-repeatability:
	@python3 scripts/run_demo_repeatability.py --runs 3
	@$(MAKE) portfolio-benchmark >/dev/null

portfolio-legacy-compatibility:
	@python3 scripts/run_legacy_compatibility.py

portfolio-check:
	@python3 scripts/portfolio_check.py

gitops-lab-up:
	@echo "GitOps lab profile ready (offline deterministic provider). For Kind + Argo CD, follow docs/demo/gitops-demo.md."

gitops-lab-status:
	@uv run --project backend --no-sync python -m app.change.demo | tail -n 10

gitops-demo:
	@uv run --project backend --no-sync python -m app.change.demo

gitops-review:
	@test -n "$(CHANGE_ID)" || (echo "CHANGE_ID is required; this command represents an external synthetic reviewer."; exit 1)
	@echo "External synthetic review recorded for $(CHANGE_ID). OpsPilot has no review or merge capability."

gitops-merge:
	@test -n "$(CHANGE_ID)" || (echo "CHANGE_ID is required; this command represents an external synthetic Git boundary."; exit 1)
	@echo "External synthetic merge requested for $(CHANGE_ID). Run the watcher to observe it."

gitops-lab-reset:
	@echo "Offline GitOps lab is in-memory and already reset."

gitops-lab-down:
	@echo "Offline GitOps lab stopped."

gitops-e2e:
	@uv run --project backend --no-sync pytest -s backend/tests/change backend/tests/architecture/test_gitops_change_boundaries.py backend/tests/test_m9_migration.py -q
	@uv run --project backend --no-sync python -m app.change.demo
