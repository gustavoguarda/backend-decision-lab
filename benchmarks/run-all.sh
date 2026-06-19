#!/usr/bin/env bash
# Sweep every implementation across every scenario with k6 — all in Docker.
#
#   ./benchmarks/run-all.sh                 # all services, all scenarios
#   ./benchmarks/run-all.sh health          # all services, one scenario
#   ./benchmarks/run-all.sh database go-gin # one scenario, one service
#
set -euo pipefail
cd "$(dirname "$0")/.."

SERVICES=(php-laravel node-fastify python-fastapi go-gin rust-axum)
SCENARIOS=(health json database cpu concurrency)

scenario="${1:-}"
service="${2:-}"

[[ -n "$scenario" ]] && SCENARIOS=("$scenario")
[[ -n "$service"  ]] && SERVICES=("$service")

echo "Ensuring stack is up..."
docker compose up --build -d "${SERVICES[@]}" postgres

for sc in "${SCENARIOS[@]}"; do
  for svc in "${SERVICES[@]}"; do
    echo
    echo "==================================================================="
    echo "  scenario=$sc  target=$svc"
    echo "==================================================================="
    TARGET="http://$svc:8000" SCENARIO="$sc" docker compose run --rm k6 || \
      echo "!! $svc/$sc failed"
  done
done

echo
echo "Done. (Tip: append '--summary-export=/results/<name>.json' inside k6 to persist.)"
