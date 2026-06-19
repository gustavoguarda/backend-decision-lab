#!/usr/bin/env bash
# Automated benchmark report: sweep every stack x scenario with k6, capture each
# run's summary + resource footprint, and generate a timestamped comparison report.
#
#   ./benchmarks/report.sh                    # full sweep, all scenarios x stacks
#   ./benchmarks/report.sh health             # one scenario, all stacks
#   ./benchmarks/report.sh database go-gin    # one scenario, one stack
#   USE_PROM=1 ./benchmarks/report.sh         # also stream live metrics to Grafana
#
# Output: reports/results/<timestamp>/  (per-run JSON, report.md, report.json)
set -euo pipefail
cd "$(dirname "$0")/.."

SERVICES=(php-laravel node-fastify python-fastapi go-gin rust-axum)
SCENARIOS=(health json database cpu concurrency)
[[ -n "${1:-}" ]] && SCENARIOS=("$1")
[[ -n "${2:-}" ]] && SERVICES=("$2")

TS=$(date +%Y%m%d-%H%M%S)
RESULTS="reports/results/$TS"
mkdir -p "$RESULTS"
USE_PROM=${USE_PROM:-0}

echo ">> Bringing up application stack..."
docker compose up -d postgres upstream "${SERVICES[@]}" >/dev/null
if [[ "$USE_PROM" == "1" ]]; then
  echo ">> Bringing up monitoring (Prometheus + Grafana)..."
  docker compose --profile monitoring up -d prometheus grafana >/dev/null
fi

# Background sampler: append "CPU%;MemUsage" once per second for one container.
sample_stats() {
  local cname="backend-decision-lab-${1}-1"
  while true; do
    docker stats --no-stream --format '{{.CPUPerc}};{{.MemUsage}}' "$cname" 2>/dev/null || true
    sleep 1
  done >> "$2"
}

for sc in "${SCENARIOS[@]}"; do
  for svc in "${SERVICES[@]}"; do
    echo ">> scenario=$sc target=$svc"
    stats_file="$RESULTS/_stats_${sc}__${svc}.csv"
    : > "$stats_file"
    sample_stats "$svc" "$stats_file" &
    sampler=$!

    k6env=(-e "TARGET=http://$svc:8000")
    [[ "$USE_PROM" == "1" ]] && k6env+=(-e "K6_OUT=experimental-prometheus-rw")

    docker compose run --rm "${k6env[@]}" k6 \
      --summary-export="/results/$TS/${sc}__${svc}.json" \
      --summary-trend-stats="avg,min,med,max,p(90),p(95),p(99)" \
      --tag "stack=$svc" --tag "scenario=$sc" --tag "testid=$TS" \
      "/scripts/${sc}.js" >/dev/null 2>&1 || echo "   !! k6 run failed for $sc/$svc"

    kill "$sampler" 2>/dev/null || true
    wait "$sampler" 2>/dev/null || true
  done
done

echo ">> Generating comparison report..."
docker run --rm \
  -v "$(pwd)/benchmarks:/app:ro" \
  -v "$(pwd)/reports:/reports" \
  python:3.12-slim python /app/generate_report.py "/reports/results/$TS" "/reports/results/$TS"

# --- Resource consumption (from docker stats samples) ---
# Reduce each stack's samples to cpu/mem avg+peak, written as TSV for reuse.
res_tsv="$RESULTS/_resources.tsv"
: > "$res_tsv"
for svc in "${SERVICES[@]}"; do
  cat "$RESULTS"/_stats_*__"${svc}".csv 2>/dev/null | awk -F';' -v stack="$svc" '
    function mib(s,   n) {
      n = s + 0
      if (s ~ /GiB/)      return n * 1024
      else if (s ~ /KiB/) return n / 1024
      else if (s ~ /MiB/) return n
      else if (s ~ /[0-9]B/) return n / 1048576
      return n
    }
    {
      cpu = $1; gsub(/%/, "", cpu); cpu += 0
      used = $2; sub(/ *\/.*/, "", used)   # "10.5MiB / 7.6GiB" -> "10.5MiB"
      mem = mib(used)
      cpu_sum += cpu; if (cpu > cpu_max) cpu_max = cpu
      mem_sum += mem; if (mem > mem_max) mem_max = mem
      n++
    }
    END {
      if (n == 0) { printf "%s\t\t\t\t\n", stack; next }
      printf "%s\t%.1f\t%.1f\t%.1f\t%.1f\n", stack, cpu_sum/n, cpu_max, mem_sum/n, mem_max
    }' >> "$res_tsv"
done

# Append the markdown table to the report, and emit resources.json for the cost model.
{
  echo ""
  echo "## Resource Consumption"
  echo ""
  echo "Sampled via \`docker stats\` once per second across all scenarios (CPU% can"
  echo "exceed 100% — it is summed across cores)."
  echo ""
  echo "| Stack | CPU % avg | CPU % peak | Mem avg (MiB) | Mem peak (MiB) |"
  echo "|-------|-----------|-----------|---------------|----------------|"
  while IFS=$'\t' read -r stack ca cp ma mp; do
    [[ -z "$ca" ]] && { echo "| $stack | n/a | n/a | n/a | n/a |"; continue; }
    echo "| $stack | $ca | $cp | $ma | $mp |"
  done < "$res_tsv"
} >> "$RESULTS/report.md"

python3 - "$res_tsv" "$RESULTS/resources.json" <<'PY'
import json, sys
tsv, out = sys.argv[1], sys.argv[2]
data = {}
for line in open(tsv):
    parts = line.rstrip("\n").split("\t")
    if not parts or not parts[0]:
        continue
    stack = parts[0]
    vals = parts[1:5]
    if any(v == "" for v in vals):
        continue
    ca, cp, ma, mp = (float(v) for v in vals)
    data[stack] = {"cpu_avg_pct": ca, "cpu_peak_pct": cp,
                   "mem_avg_mib": ma, "mem_peak_mib": mp}
json.dump(data, open(out, "w"), indent=2)
PY

# Clean up raw samples (keep JSON summaries + report + resources.json).
rm -f "$RESULTS"/_stats_*.csv "$res_tsv"

echo ""
echo ">> Done. Report: $RESULTS/report.md"
echo ">> Raw summaries + report.json: $RESULTS/"
[[ "$USE_PROM" == "1" ]] && echo ">> Live dashboards: Grafana http://localhost:${GRAFANA_PORT:-3001} (k6 Load Test)"
