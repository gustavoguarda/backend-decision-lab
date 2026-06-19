#!/usr/bin/env bash
# Horizontal-scaling benchmark (Phase 4, local simulation).
# Scales one stack to N replicas behind Docker's round-robin DNS and measures how
# throughput grows. Reports the scaling factor and efficiency per replica count.
#
#   ./benchmarks/scale.sh go-gin            # default replica counts: 1 2 4
#   ./benchmarks/scale.sh node-fastify 1 2 4 8
#   ./benchmarks/scale.sh rust-axum 1 3
#
set -euo pipefail
cd "$(dirname "$0")/.."

STACK="${1:-go-gin}"
shift || true
REPLICAS=("$@")
[[ ${#REPLICAS[@]} -eq 0 ]] && REPLICAS=(1 2 4)

PROJECT=bdl-scale
COMPOSE=(docker compose -p "$PROJECT" -f docker-compose.scale.yml)
NET="${PROJECT}_lab"

TS=$(date +%Y%m%d-%H%M%S)
OUT="reports/results/scale-$TS"
mkdir -p "$OUT"

echo ">> Scaling benchmark: $STACK at replicas ${REPLICAS[*]}"
"${COMPOSE[@]}" build "$STACK" >/dev/null
"${COMPOSE[@]}" up -d postgres upstream >/dev/null

wait_health() {
  for _ in $(seq 1 90); do
    if docker run --rm --network "$NET" curlimages/curl:latest \
         -s -o /dev/null --max-time 2 "http://$STACK:8000/health"; then return 0; fi
    sleep 1
  done
  return 1
}

for n in "${REPLICAS[@]}"; do
  echo ">> --- $STACK x $n replica(s) ---"
  "${COMPOSE[@]}" up -d --scale "$STACK=$n" "$STACK" >/dev/null
  echo "   waiting for replicas..."
  if ! wait_health; then echo "   !! $STACK never became healthy"; continue; fi
  sleep 3   # let all replicas settle into the DNS rotation
  "${COMPOSE[@]}" run --rm -e "TARGET=http://$STACK:8000" k6 \
    --summary-export="/results/scale-$TS/${STACK}__${n}.json" \
    /scripts/health.js >/dev/null 2>&1 || echo "   !! k6 run failed"
  rps=$(python3 -c "import json;print(round(json.load(open('$OUT/${STACK}__${n}.json'))['metrics']['http_reqs']['rate']))" 2>/dev/null || echo 0)
  echo "   RPS @ ${n}: $rps"
done

echo ">> Tearing down scaling project..."
"${COMPOSE[@]}" down >/dev/null 2>&1 || true

# --- Build scaling report (Markdown + JSON) ---
python3 - "$STACK" "$OUT" "${REPLICAS[@]}" <<'PY'
import json, sys, os
stack, outdir, *reps = sys.argv[1:]
reps = [int(r) for r in reps]
rows = []
for n in reps:
    p = os.path.join(outdir, f"{stack}__{n}.json")
    if not os.path.exists(p):
        continue
    try:
        m = json.load(open(p))["metrics"]
        rows.append({"replicas": n,
                     "rps": round(m["http_reqs"]["rate"]),
                     "p95_ms": round(m.get("http_req_duration", {}).get("p(95)", 0), 2)})
    except Exception as e:
        print(f"warn: {p}: {e}", file=sys.stderr)

base = rows[0]["rps"] if rows else 0
md = [f"# Horizontal Scaling — {stack}", "",
      "Throughput as replica count increases (Docker DNS round-robin). "
      "Scaling factor = RPS(n) / RPS(base); efficiency = factor / (n / base_replicas).", "",
      "| Replicas | RPS | p95 (ms) | Scaling factor | Efficiency |",
      "|---------:|----:|---------:|---------------:|-----------:|"]
base_rep = rows[0]["replicas"] if rows else 1
for r in rows:
    factor = (r["rps"] / base) if base else 0
    ideal = r["replicas"] / base_rep
    eff = (factor / ideal) if ideal else 0
    md.append(f"| {r['replicas']} | {r['rps']:,} | {r['p95_ms']} | {factor:.2f}x | {eff*100:.0f}% |")
md.append("")
md.append("> Efficiency near 100% means throughput scales linearly with replicas; "
          "lower values indicate a shared bottleneck (often the single Postgres or host CPU).")

open(os.path.join(outdir, "scaling.md"), "w").write("\n".join(md) + "\n")
json.dump({"stack": stack, "results": rows}, open(os.path.join(outdir, "scaling.json"), "w"), indent=2)
print("\n".join(md))
print(f"\n>> Wrote {outdir}/scaling.md and scaling.json")
PY
