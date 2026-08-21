#!/usr/bin/env bash
set -euo pipefail

profile="${1:-}"
if [[ "$profile" != "minimal" && "$profile" != "full" ]]; then
  echo "Usage: scripts/demo_compose.sh minimal|full" >&2
  exit 2
fi

compose=(docker compose -f lab/docker-compose.yml)
core=(postgres dependency web-01 web-02 prometheus loki promtail)
log_file="$(mktemp)"
trap 'rm -f "$log_file"' EXIT

if [[ "$profile" == "minimal" ]]; then
  compose_profile="demo-minimal"
  runner="lab-runner-minimal"
  services=("${core[@]}")
else
  compose_profile="demo-full"
  runner="lab-runner-full"
  services=("${core[@]}" qdrant mcp-server)
fi

if ! "${compose[@]}" --profile "$compose_profile" build "${services[@]}" "$runner" >"$log_file" 2>&1; then
  echo "Demo image build failed. Last output:" >&2
  tail -40 "$log_file" >&2
  exit 1
fi

if ! "${compose[@]}" --profile "$compose_profile" up -d --no-build --wait "${services[@]}" >"$log_file" 2>&1; then
  echo "Demo startup failed. Last output:" >&2
  tail -40 "$log_file" >&2
  echo "Run make demo-reset, verify ports with make demo-doctor, then retry." >&2
  exit 1
fi

echo "Demo containers ready ($compose_profile)."
