# Backend Decision Lab

A technology evaluation framework for backend architecture decisions, driven by
**measurable data** instead of personal preference. The same set of endpoints is
implemented across multiple stacks and benchmarked under identical conditions so
teams can reason about real trade-offs: performance, resource cost, productivity,
operational complexity, and team impact.

> There is no universally best backend technology — only the most appropriate one
> for a given context.

## Technologies evaluated

| Language | Framework | Host port |
|----------|-----------|-----------|
| PHP      | Laravel   | 8001      |
| Node.js  | Fastify   | 8002      |
| Python   | FastAPI   | 8003      |
| Go       | Gin       | 8004      |
| Rust     | Axum      | 8005      |

## Everything runs in Docker

No language toolchains on your host — only Docker + Docker Compose. Each stack, the
Postgres database, and the k6 load generator all run as containers.

```bash
cp .env.example .env

# Build and start Postgres + all five services
docker compose up --build -d

# Sanity-check an endpoint (Go on 8004)
curl localhost:8004/health      # {"status":"ok"}
curl localhost:8004/serialize   # static JSON
curl localhost:8004/users/123   # DB-backed -> John Doe
```

## Benchmark scenarios

Each service exposes the same contract (see [`docs/CONTRACT.md`](docs/CONTRACT.md)):

| # | Scenario          | Endpoint            | Measures                  |
|---|-------------------|---------------------|---------------------------|
| 1 | Health check      | `GET /health`       | Raw framework overhead    |
| 2 | JSON serialization| `GET /serialize`    | Serialization, no DB      |
| 3 | Database access   | `GET /users/{id}`   | Driver/ORM + index lookup |
| 4 | CPU intensive     | `GET /cpu/{rounds}` | Chained SHA-256 throughput|
| 5 | Concurrency       | `GET /aggregate`    | Async fan-out (10 calls)  |

Scenario 5 calls a mock `upstream` service (`go-httpbin`, `/delay/0.05`) defined in
compose, so concurrency is measured without depending on the public internet.

## Running the benchmarks (k6, also in Docker)

The k6 service takes two variables: `TARGET` (which service) and `SCENARIO` (which script).

```bash
# Health check against Go/Gin
TARGET=http://go-gin:8000 SCENARIO=health docker compose run --rm k6

# Database scenario against Node/Fastify
TARGET=http://node-fastify:8000 SCENARIO=database docker compose run --rm k6
```

Available `SCENARIO` values: `health`, `json`, `database`, `cpu`, `concurrency`
(scripts in `k6/`). The `cpu` script accepts `ROUNDS` (default `50000`).
Service names usable as `TARGET`: `php-laravel`, `node-fastify`, `python-fastapi`,
`go-gin`, `rust-axum` — all on internal port `8000`.

### Sweep every stack for one scenario

```bash
for svc in php-laravel node-fastify python-fastapi go-gin rust-axum; do
  echo "=== $svc ==="
  TARGET=http://$svc:8000 SCENARIO=health docker compose run --rm k6
done
```

## Automated reports

`benchmarks/report.sh` runs a full sweep (every stack × scenario), captures each
run's k6 summary and a `docker stats` resource footprint, and generates a
timestamped comparison report — all in Docker.

```bash
./benchmarks/report.sh                  # full sweep (all scenarios × stacks)
./benchmarks/report.sh health           # one scenario, all stacks
./benchmarks/report.sh database go-gin  # one scenario, one stack
USE_PROM=1 ./benchmarks/report.sh       # also stream live metrics to Grafana
```

Output lands in `reports/results/<timestamp>/`:
- `report.md` — per-scenario tables (RPS, avg/p95/p99 latency, error %), a
  throughput ranking, and a resource-consumption table (CPU %, memory).
- `report.json` — the same data, machine-readable.
- `<scenario>__<stack>.json` — the raw k6 summary for each run.

Each run is its own timestamped directory, so reports accumulate as history.

📊 **See [`reports/example/`](reports/example/) for a complete sample run** — all
five scenarios across all five stacks, plus cost, deploy-footprint, and scaling
results, with notes on the test environment.

## Monitoring (Grafana + Prometheus)

An opt-in monitoring profile streams live k6 metrics to Prometheus (via k6's
native remote write) and visualizes them in a provisioned Grafana dashboard.

```bash
docker compose --profile monitoring up -d        # start Prometheus + Grafana
USE_PROM=1 ./benchmarks/report.sh health          # run benchmarks, push metrics
```

- **Grafana**: http://localhost:3001 (default `admin` / `admin`; anonymous
  viewing enabled). Dashboard: **k6 Load Test** — RPS, p95/p99 latency, error and
  check rates, and VUs, all grouped by stack so the five overlay for comparison.
- **Prometheus**: http://localhost:9090 (30-day retention → historical tracking).

> Resource metrics (CPU/memory) come from `docker stats` in the report rather than
> cAdvisor, which cannot see per-container cgroups on Docker Desktop.

## Cost, scaling & deploy footprint (Phase 4 — local simulation)

These model cloud decisions from locally-measured data — no cloud account required.

### Horizontal scaling

Scales one stack to N replicas (behind Docker's round-robin DNS, isolated in the
`bdl-scale` Compose project) and measures how throughput grows:

```bash
./benchmarks/scale.sh go-gin 1 2 4     # writes scaling.md / scaling.json
```

Reports RPS, scaling factor, and efficiency per replica count. On a single host,
efficiency falls off once the host CPU saturates — the signal that real gains need
a multi-node cluster, not a bigger box.

### Cost model

Combines measured throughput + peak resource usage with a pricing config to model
cost efficiency (`$/1M requests`, `$/month` at a target load) across cloud profiles:

```bash
# After a report run (needs report.json + resources.json):
python3 benchmarks/cost_model.py reports/results/<timestamp> benchmarks/pricing.json
```

Prices live in `benchmarks/pricing.json` (AWS Fargate, GCP Cloud Run, generic VM).
It's an efficiency estimate from real measurements — not a cloud bill.

### Deploy footprint

Measures image size and cold-start time (proxy for serverless suitability):

```bash
./benchmarks/deploy_metrics.sh        # writes deploy.md / deploy.json
```

## Project structure

```
backend-decision-lab/
├── implementations/        # one folder per stack, each self-contained + Dockerfile
│   ├── php-laravel/
│   ├── node-fastify/
│   ├── python-fastapi/
│   ├── go-gin/
│   └── rust-axum/
├── infrastructure/
│   ├── postgres/init.sql   # shared schema + seed (10k users)
│   └── monitoring/         # prometheus config + grafana provisioning/dashboards
├── k6/                     # load test scripts (one per scenario)
├── benchmarks/
│   ├── run-all.sh          # quick sweep (prints k6 summaries to stdout)
│   ├── report.sh           # full sweep -> timestamped comparison report
│   ├── generate_report.py  # k6 summaries -> report.md / report.json
│   ├── scale.sh            # horizontal scaling benchmark (N replicas)
│   ├── cost_model.py       # cost efficiency model + pricing.json
│   └── deploy_metrics.sh   # image size + cold-start footprint
├── docs/CONTRACT.md        # the contract every implementation must satisfy
├── reports/results/        # timestamped benchmark output (history)
├── docker-compose.yml      # main stack
└── docker-compose.scale.yml # isolated harness for scaling benchmark
```

## Decision matrix

Performance is only one input. Each stack is scored on a weighted scorecard:

| Category               | Weight |
|------------------------|--------|
| Performance            | 25%    |
| Scalability            | 20%    |
| Developer Productivity | 20%    |
| Operational Complexity | 15%    |
| Team Availability      | 10%    |
| Learning Curve         | 10%    |

Scores are scenario-dependent and are **not** universal rankings.

## Roadmap

- **Phase 1** — Docker env, Postgres, health/serialize/database endpoints, k6 ✅
- **Phase 2** — CPU and concurrency scenarios ✅
- **Phase 3** — Automated reports, Grafana dashboards, historical tracking ✅
- **Phase 4** — Cost analysis, deploy footprint, horizontal scaling (local sim) ✅

## License

MIT
