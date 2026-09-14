#!/usr/bin/env bash
# Start the CogniBot stack, open the dashboard, follow the logs; Ctrl-C stops everything.
#
#   ./start.sh            # full: sim + MoveIt + dashboard + VLM agent + VLA policy server
#   ./start.sh core       # sim + MoveIt + bridge + dashboard only
#   ./start.sh vlm        # core + llama-swap + VLM agent (Agent tab)
#   ./start.sh vla        # core + LeRobot policy server + skill executor (VLA tab)
#   ./start.sh full --no-browser
#
# First time: `make env`, `make build`, cognibot_ws/docker/llm/download_model.sh (vlm) and
# cognibot_ws/src/cognibot_vla/scripts/download_checkpoints.sh (vla).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

COMPOSE=(docker compose -f cognibot_ws/docker/docker-compose.yml)
DASHBOARD_URL=http://127.0.0.1:8000
profile=full
open_browser=true
for arg in "$@"; do
  case "${arg}" in
    core | vlm | vla | full) profile="${arg}" ;;
    --no-browser) open_browser=false ;;
    -h | --help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "unknown argument: ${arg}" >&2; exit 2 ;;
  esac
done

profile_args=()
[ "${profile}" != core ] && profile_args=(--profile "${profile}")

stopping=false
stop() {
  # Runs on Ctrl-C, SIGTERM and normal exit; idempotent.
  ${stopping} && return
  stopping=true
  trap - INT TERM EXIT
  echo
  echo ">>> stopping every CogniBot service (all profiles)"
  "${COMPOSE[@]}" --profile full --profile twin down --remove-orphans
  if command -v nvidia-smi >/dev/null; then
    echo ">>> GPU: $(nvidia-smi --query-gpu=temperature.gpu,memory.used --format=csv,noheader)"
  fi
}
trap stop INT TERM EXIT

echo ">>> starting profile '${profile}'"
"${COMPOSE[@]}" "${profile_args[@]}" up -d

echo -n ">>> waiting for the dashboard"
for _ in $(seq 1 60); do
  if curl -fsS -o /dev/null "${DASHBOARD_URL}"; then break; fi
  echo -n .
  sleep 1
done
echo
"${COMPOSE[@]}" "${profile_args[@]}" ps --format "table {{.Service}}\t{{.Status}}"
echo
echo ">>> dashboard: ${DASHBOARD_URL}   (F1 camera · F2 motion · F3 agent · F4 VLA · F5 system)"
echo ">>> Ctrl-C stops all containers"
if ${open_browser} && command -v xdg-open >/dev/null; then
  xdg-open "${DASHBOARD_URL}" >/dev/null 2>&1 || true
fi

# Follow the agent-level services; the simulator and MoveIt are chatty and stay in `make logs`.
follow=(motion)
case "${profile}" in
  vlm) follow+=(vlm-agent) ;;
  vla) follow+=(vla-client) ;;
  full) follow+=(vlm-agent vla-client) ;;
esac
"${COMPOSE[@]}" "${profile_args[@]}" logs -f --tail 5 "${follow[@]}" || true
