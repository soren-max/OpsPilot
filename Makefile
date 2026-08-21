.PHONY: demo lab-up lab-inject lab-status lab-reset lab-down lab-demo memory-index memory-eval mcp-demo mcp-eval

LAB_CLI_ENV = OPSPILOT_SECRET_KEY=lab-cli-only-secret-key-at-least-32-characters

demo:
	@uv run --project backend --no-sync python -m app.demo

lab-up:
	docker compose -f lab/docker-compose.yml up -d --build postgres qdrant dependency web-01 web-02 prometheus loki promtail

lab-inject:
	@$(LAB_CLI_ENV) uv run --project backend --no-sync python -m app.lab inject "$(SCENARIO)"

lab-status:
	@$(LAB_CLI_ENV) uv run --project backend --no-sync python -m app.lab status

lab-reset:
	@$(LAB_CLI_ENV) uv run --project backend --no-sync python -m app.lab reset

lab-down:
	docker compose -f lab/docker-compose.yml --profile demo down -v --remove-orphans

lab-demo: lab-down lab-up
	docker compose -f lab/docker-compose.yml --profile demo run --rm --build lab-runner
	docker compose -f lab/docker-compose.yml --profile demo run --rm lab-runner python -m app.lab reset

memory-index:
	uv run --project backend --no-sync python -m app.memory.index

memory-eval:
	uv run --project backend --no-sync python -m app.memory.eval --json-output evals/incident-memory/results.json

mcp-eval:
	uv run --project backend --no-sync python -m app.mcp_eval

mcp-demo:
	uv run --project backend --no-sync pytest backend/tests/mcp/test_mcp_server.py backend/tests/mcp/test_mcp_transports.py -q
	$(MAKE) mcp-eval
