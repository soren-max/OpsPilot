#!/usr/bin/env bash
set -Eeuo pipefail

action="${1:-}"
environment="${2:-}"
host="${3:-}"
service="${4:-}"

if [[ ! "${action}" =~ ^(status|start|stop)$ ]]; then
  printf '{"state":"failed","message":"unsupported action"}\n'
  exit 64
fi

case "${service}" in
  timeout)
    printf 'started\n'
    sleep 30
    ;;
  ignore-term)
    trap '' TERM
    printf 'ignoring term\n'
    sleep 30
    ;;
  large-output)
    yes 'fixture output TOKEN=fixture-secret password=fixture-password' | head -n 20000
    ;;
  invalid-encoding)
    printf '\377\376{"state":"running"}\n'
    ;;
  unreachable)
    printf '{"state":"unreachable","message":"host unreachable"}\n'
    exit 4
    ;;
  not-found)
    printf '{"state":"not_found","message":"service not found"}\n'
    exit 5
    ;;
  non-zero)
    printf 'partial stdout\n'
    printf 'ansible failed\n' >&2
    exit 7
    ;;
  failed)
    printf 'partial stdout TOKEN=fixture-secret\n'
    printf 'ansible failed password=fixture-password\n' >&2
    exit 7
    ;;
  partial-success)
    if [[ "${host}" == *fail* ]]; then
      printf '{"state":"failed","message":"partial target failed"}\n'
      exit 9
    fi
    ;;
  warning)
    printf 'redacted warning\n' >&2
    ;;
  unknown)
    printf 'unrecognized output for %s/%s\n' "${environment}" "${host}"
    exit 0
    ;;
esac

state_directory="${PWD}/.fake-services-state"
state_key="${environment}__${host}__${service}"
state_file="${state_directory}/${state_key}"

if [[ "${action}" == "start" || "${action}" == "stop" ]]; then
  mkdir -p "${state_directory}"
  next_state="running"
  [[ "${action}" == "stop" ]] && next_state="stopped"
  temporary="${state_file}.$$"
  printf '%s\n' "${next_state}" > "${temporary}"
  mv "${temporary}" "${state_file}"
  printf '{"state":"%s","message":"%s completed"}\n' "${next_state}" "${action}"
  exit 0
fi

state="running"
[[ "${service}" == "stopped" ]] && state="stopped"
if [[ -f "${state_file}" ]]; then
  state="$(<"${state_file}")"
fi
printf '{"state":"%s","message":"service is %s"}\n' "${state}" "${state}"
