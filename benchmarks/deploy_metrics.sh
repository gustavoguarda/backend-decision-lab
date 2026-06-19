#!/usr/bin/env bash
# Deployment-footprint benchmark (Phase 4 "cloud deployment footprint", local simulation).
# Measures two cloud/serverless-relevant metrics per stack:
#   1. Image size     - built Docker image size in MB (registry cost, pull time, cold-start weight).
#   2. Cold-start time - ms from container start until GET /health first returns HTTP 200
#                        (serverless cold-start proxy; image pull excluded, image is already local).
#
#   ./benchmarks/deploy_metrics.sh                       # all five stacks
#   ./benchmarks/deploy_metrics.sh go-gin rust-axum      # a subset
#
set -euo pipefail
cd "$(dirname "$0")/.."

ALL_STACKS=(php-laravel node-fastify python-fastapi go-gin rust-axum)
STACKS=("$@")
[[ ${#STACKS[@]} -eq 0 ]] && STACKS=("${ALL_STACKS[@]}")

NET="backend-decision-lab_lab"
TS=$(date +%Y%m%d-%H%M%S)
OUT="reports/results/deploy-$TS"
mkdir -p "$OUT"

# High-resolution wall clock (date +%s.%N is unreliable on macOS/BSD).
now() { python3 -c 'import time; print(time.time())'; }

echo ">> Deployment-footprint benchmark for: ${STACKS[*]}"

# Ensure all requested images exist, building any that are missing.
for stack in "${STACKS[@]}"; do
  img="backend-decision-lab-$stack"
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    echo ">> Image $img missing - building..."
    docker compose build "$stack" || echo "   !! build failed for $stack"
  fi
done

# Dependencies some apps need at boot to serve /health (e.g. python-fastapi waits for the DB pool).
echo ">> Bringing up postgres + upstream..."
docker compose up -d postgres upstream >/dev/null 2>&1 || echo "   !! could not start postgres/upstream"

# Collected results, kept as parallel files so a failing stack never aborts the run.
RESULTS_TSV="$OUT/.results.tsv"   # stack \t image_mb \t cold_ms(or "null")
: >"$RESULTS_TSV"

measure_stack() {
  local stack="$1"
  local img="backend-decision-lab-$stack"
  local image_mb="null" cold_ms="null"

  echo ">> --- $stack ---"

  # --- Image size ---
  local bytes
  if bytes=$(docker image inspect "$img" --format '{{.Size}}' 2>/dev/null) && [[ -n "$bytes" ]]; then
    image_mb=$(python3 -c "print(round($bytes/1000000, 1))")
    echo "   image size: ${image_mb} MB"
  else
    echo "   !! could not inspect image $img"
  fi

  # --- Cold start ---
  local cid="" hostport="" start end code
  start=$(now)
  if cid=$(docker run -d --rm \
            --network "$NET" \
            -p 127.0.0.1:0:8000 \
            -e DB_HOST=postgres -e DB_PORT=5432 \
            -e DB_NAME=benchmark -e DB_USER=benchmark -e DB_PASSWORD=benchmark \
            -e APP_PORT=8000 \
            -e UPSTREAM_URL=http://upstream:8080 \
            "$img" 2>/dev/null) && [[ -n "$cid" ]]; then

    hostport=$(docker port "$cid" 8000/tcp 2>/dev/null | head -1 | sed 's/.*://')
    if [[ -n "$hostport" ]]; then
      # Poll /health until HTTP 200 or ~60s timeout (600 * 0.1s).
      local i
      for ((i = 0; i < 600; i++)); do
        code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 \
                 "http://127.0.0.1:$hostport/health" 2>/dev/null || echo 000)
        if [[ "$code" == "200" ]]; then
          end=$(now)
          cold_ms=$(python3 -c "print(round(($end - $start) * 1000))")
          echo "   cold start: ${cold_ms} ms"
          break
        fi
        sleep 0.1
      done
      [[ "$cold_ms" == "null" ]] && echo "   !! $stack /health never returned 200 within ~60s (cold start = n/a)"
    else
      echo "   !! could not resolve mapped host port for $stack"
    fi

    docker stop "$cid" >/dev/null 2>&1 || true   # --rm self-removes
  else
    echo "   !! could not start container for $stack"
  fi

  printf '%s\t%s\t%s\n' "$stack" "$image_mb" "$cold_ms" >>"$RESULTS_TSV"
}

for stack in "${STACKS[@]}"; do
  # Guard each stack so one failure (e.g. cold-start timeout) cannot abort the rest.
  measure_stack "$stack" || echo "   !! unexpected error measuring $stack (continuing)"
done

# --- Write reports (deploy.md + deploy.json) from the collected TSV ---
python3 - "$RESULTS_TSV" "$OUT" "$TS" <<'PY'
import json, sys, datetime

tsv_path, out_dir, ts = sys.argv[1], sys.argv[2], sys.argv[3]

rows = []
with open(tsv_path) as f:
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        stack, image_mb, cold_ms = line.split("\t")
        rows.append({
            "stack": stack,
            "image_mb": None if image_mb == "null" else float(image_mb),
            "cold_ms": None if cold_ms == "null" else int(cold_ms),
        })

# Sort by image size ascending; unknown sizes sink to the bottom.
rows.sort(key=lambda r: (r["image_mb"] is None, r["image_mb"] if r["image_mb"] is not None else 0))

# Identify the smallest image and fastest cold start (ignoring unknowns).
sizes = [r["image_mb"] for r in rows if r["image_mb"] is not None]
colds = [r["cold_ms"] for r in rows if r["cold_ms"] is not None]
min_size = min(sizes) if sizes else None
min_cold = min(colds) if colds else None

def fmt_size(r):
    if r["image_mb"] is None:
        return "n/a"
    s = f"{r['image_mb']:.1f}"
    return f"**{s}**" if r["image_mb"] == min_size else s

def fmt_cold(r):
    if r["cold_ms"] is None:
        return "n/a"
    s = str(r["cold_ms"])
    return f"**{s}**" if r["cold_ms"] == min_cold else s

generated_at = datetime.datetime.now().isoformat(timespec="seconds")

md = []
md.append("# Deployment footprint")
md.append("")
md.append(f"_Generated {generated_at}. Image size = registry/pull cost; "
          "cold start = container boot until GET /health returns 200 (image already local). "
          "Smallest image and fastest cold start in **bold**._")
md.append("")
md.append("| Stack | Image size (MB) | Cold start (ms) |")
md.append("| --- | ---: | ---: |")
for r in rows:
    md.append(f"| {r['stack']} | {fmt_size(r)} | {fmt_cold(r)} |")
md.append("")
with open(f"{out_dir}/deploy.md", "w") as f:
    f.write("\n".join(md))

payload = {
    "generated_at": generated_at,
    "stacks": {
        r["stack"]: {"image_mb": r["image_mb"], "cold_start_ms": r["cold_ms"]}
        for r in rows
    },
}
with open(f"{out_dir}/deploy.json", "w") as f:
    json.dump(payload, f, indent=2)
    f.write("\n")
PY

rm -f "$RESULTS_TSV"

echo ""
echo ">> Report written to: $OUT/deploy.md"
echo "   (also $OUT/deploy.json)"
