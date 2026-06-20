# Example Benchmark Results

A complete sample run, committed so the framework's output is visible without
running it yourself. Regenerate any of these with the scripts in
[`../../benchmarks/`](../../benchmarks).

> **These numbers are machine-dependent.** They were produced on a single
> developer machine, not isolated cloud hardware. The **relative** comparison
> between stacks is the signal; treat absolute RPS as illustrative, not a
> universal ranking.

## Environment

- Docker Desktop on macOS (Apple Silicon), engine allocated **4 vCPU / 7 GB RAM**
- All services, the database, the load generator, and the upstream mock run as
  containers on the same host (they share those 4 vCPUs — which is why absolute
  throughput is lower than dedicated hardware and why horizontal scaling on one
  host saturates quickly)
- Generated 2026-06-20

## Files

| File | What it is | Produced by |
|------|------------|-------------|
| `report.md` / `report.json` | Per-scenario comparison (RPS, p95/p99, errors) + throughput ranking + resource table | `report.sh` → `generate_report.py` |
| `resources.json` | Per-stack CPU% / memory footprint (docker stats) | `report.sh` |
| `cost.md` / `cost.json` | Modeled cost ($/1M requests, $/month) across cloud profiles | `cost_model.py` |
| `deploy.md` / `deploy.json` | Image size + cold-start time per stack | `deploy_metrics.sh` |
| `scaling.md` / `scaling.json` | Throughput vs replica count for go-gin (1→2→4) | `scale.sh` |

## Highlights from this run

- **Throughput:** rust-axum and go-gin lead almost every scenario; go-gin edges
  ahead on the database workload.
- **CPU-bound work:** node-fastify collapses to ~29 RPS on the `cpu` scenario —
  chained SHA-256 blocks the single-threaded event loop, while Go/Rust/Python/PHP
  spread it across cores/workers. A textbook trade-off this lab exists to surface.
- **Footprint:** go-gin ships a 4.6 MB image with a ~150 ms cold start;
  php-laravel is ~261 MB and ~1.7 s — a large gap for serverless suitability.
- **Cost:** rust-axum and go-gin are the most cost-efficient per request because
  they pair high throughput with a tiny (~10 MiB) memory footprint.
- **Scaling:** on a single 4-vCPU host, adding replicas does not increase
  throughput once CPU saturates — the signal that real gains need a multi-node
  cluster, not a bigger box.
