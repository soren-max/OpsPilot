#!/bin/sh
set -eu

operation="${1:-}"
service="${2:-}"
state_file=/var/lib/opspilot-demo/demo-api.state

if [ "$service" != "demo-api" ] && [ "$service" != "demo-worker" ]; then
  echo "service is not allowlisted" >&2
  exit 2
fi

case "$operation" in
  start|restart)
    printf '%s\n' running > "$state_file"
    ;;
  stop)
    printf '%s\n' stopped > "$state_file"
    ;;
  status)
    [ "$(cat "$state_file" 2>/dev/null || true)" = "running" ]
    ;;
  *)
    echo "operation is not allowlisted" >&2
    exit 2
    ;;
esac
