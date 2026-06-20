# Backend Decision Lab

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![k6](https://img.shields.io/badge/load%20testing-k6-7D64FF?logo=k6&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-F46800?logo=grafana&logoColor=white)
![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?logo=prometheus&logoColor=white)

![Go](https://img.shields.io/badge/Go-00ADD8?logo=go&logoColor=white)
![Rust](https://img.shields.io/badge/Rust-000000?logo=rust&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-5FA04E?logo=nodedotjs&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![PHP](https://img.shields.io/badge/PHP-777BB4?logo=php&logoColor=white)

A technology evaluation framework for backend architecture decisions, driven by
**measurable data** instead of personal preference. The same endpoints are
implemented across five stacks and benchmarked under identical conditions, so
teams can reason about real trade-offs: performance, resource cost, and operational fit.

> There is no universally best backend technology — only the most appropriate one
> for a given context.

## Technologies evaluated

| Language | Framework | Host port |
| -------- | --------- | --------- |
| PHP      | Laravel   | 8001      |
| Node.js  | Fastify   | 8002      |
| Python   | FastAPI   | 8003      |
| Go       | Gin       | 8004      |
| Rust     | Axum      | 8005      |

## Results

A full sample run (4 vCPU / 7 GB Docker host) — **relative comparison is the
signal; absolute numbers are machine-dependent.** Full data in
[`reports/example/`](reports/example/).

**Throughput ranking** (average rank across all five scenarios, lower is better):

| Stack            | Avg rank | Strongest scenarios          |
| ---------------- | -------: | ---------------------------- |
| Go / Gin         |      1.4 | database (31k RPS), CPU      |
| Rust / Axum      |      1.6 | health (76k RPS), JSON       |
| Node / Fastify   |      3.4 | I/O-bound; weak on CPU       |
| Python / FastAPI |      4.0 | consistent, lower throughput |
| PHP / Laravel    |      4.6 | heaviest CPU/memory use      |

**Trade-offs the data surfaces:**

- **CPU-bound work:** Node/Fastify drops to ~29 RPS on the CPU scenario — chained
  SHA-256 blocks the single-threaded event loop, while Go/Rust/Python/PHP spread
  it across cores/workers.
- **Deploy footprint:** Go ships a 4.6 MB image with a ~150 ms cold start;
  Laravel is ~261 MB and ~1.7 s — a wide gap for serverless suitability.
- **Cost efficiency:** Rust and Go are cheapest per request (high throughput plus
  a ~10 MiB memory footprint).
- **Horizontal scaling:** on a single host, throughput stops growing once CPU
  saturates — real gains need a multi-node cluster, not a bigger box.

## Quickstart

Only Docker + Docker Compose required — no language toolchains on your host.

```bash
cp .env.example .env
docker compose up --build -d        # Postgres + all five services

curl localhost:8004/health          # Go/Gin → {"status":"ok"}
curl localhost:8004/users/123       # DB-backed → John Doe
```

## Benchmarks

Each service implements the same five scenarios behind one contract
([`docs/CONTRACT.md`](docs/CONTRACT.md)):

| #   | Scenario           | Endpoint            | Measures                   |
| --- | ------------------ | ------------------- | -------------------------- |
| 1   | Health check       | `GET /health`       | Raw framework overhead     |
| 2   | JSON serialization | `GET /serialize`    | Serialization, no DB       |
| 3   | Database access    | `GET /users/{id}`   | Driver/ORM + index lookup  |
| 4   | CPU intensive      | `GET /cpu/{rounds}` | Chained SHA-256 throughput |
| 5   | Concurrency        | `GET /aggregate`    | Async fan-out (10 calls)   |

Run one scenario against one stack:

```bash
TARGET=http://go-gin:8000 SCENARIO=health docker compose run --rm k6
```

Run the full sweep → a timestamped comparison report (RPS, p95/p99, errors, resources):

```bash
./benchmarks/report.sh
```

Also available, all in Docker: live Grafana dashboards
(`docker compose --profile monitoring up -d` + `USE_PROM=1 ./benchmarks/report.sh`),
a cloud cost model (`benchmarks/cost_model.py`), deploy footprint
(`benchmarks/deploy_metrics.sh`), and horizontal scaling (`benchmarks/scale.sh`).
Sample output in [`reports/example/`](reports/example/).

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
├── benchmarks/             # report, cost model, deploy footprint, scaling
├── docs/CONTRACT.md        # the contract every implementation must satisfy
├── reports/example/        # sample benchmark output
├── docker-compose.yml      # main stack
└── docker-compose.scale.yml # isolated harness for scaling benchmark
```

## License

MIT — see [LICENSE](LICENSE).
