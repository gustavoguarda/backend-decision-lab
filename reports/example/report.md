# Benchmark Comparison Report

Generated at: 2026-06-20T16:14:49

## Scenario: health

| Stack | RPS | avg (ms) | p95 (ms) | p99 (ms) | errors % |
| --- | ---: | ---: | ---: | ---: | ---: |
| rust-axum | **76,348** | **0.61** | **1.84** | **3.47** | **0.00** |
| go-gin | 63,715 | 0.74 | 2.24 | 4.09 | **0.00** |
| node-fastify | 41,110 | 1.18 | 2.35 | 4.48 | **0.00** |
| python-fastapi | 23,999 | 2.02 | 5.20 | 9.11 | **0.00** |
| php-laravel | 5,680 | 8.74 | 17.18 | 30.05 | **0.00** |

## Scenario: json

| Stack | RPS | avg (ms) | p95 (ms) | p99 (ms) | errors % |
| --- | ---: | ---: | ---: | ---: | ---: |
| rust-axum | **60,469** | **0.76** | **2.34** | **4.64** | **0.00** |
| go-gin | 54,095 | 0.87 | 2.63 | 4.96 | **0.00** |
| node-fastify | 36,166 | 1.34 | 2.95 | 5.99 | **0.00** |
| python-fastapi | 22,810 | 2.12 | 5.43 | 9.43 | **0.00** |
| php-laravel | 5,803 | 8.56 | 15.24 | 19.64 | **0.00** |

## Scenario: database

| Stack | RPS | avg (ms) | p95 (ms) | p99 (ms) | errors % |
| --- | ---: | ---: | ---: | ---: | ---: |
| go-gin | **31,353** | **1.53** | **3.97** | **6.54** | **0.00** |
| rust-axum | 27,535 | 1.74 | 4.26 | 6.99 | **0.00** |
| node-fastify | 16,138 | 3.04 | 5.12 | 8.65 | **0.00** |
| python-fastapi | 10,985 | 4.47 | 9.43 | 14.47 | **0.00** |
| php-laravel | 4,348 | 11.43 | 17.22 | 22.89 | **0.00** |

## Scenario: cpu

| Stack | RPS | avg (ms) | p95 (ms) | p99 (ms) | errors % |
| --- | ---: | ---: | ---: | ---: | ---: |
| go-gin | **1,558** | **12.80** | 60.49 | 83.16 | **0.00** |
| rust-axum | 509 | 39.23 | **58.49** | **68.69** | **0.00** |
| python-fastapi | 216 | 92.57 | 159.31 | 244.16 | **0.00** |
| php-laravel | 151 | 132.40 | 159.81 | 179.11 | **0.00** |
| node-fastify | 29 | 691.67 | 1262.33 | 2032.97 | **0.00** |

## Scenario: concurrency

| Stack | RPS | avg (ms) | p95 (ms) | p99 (ms) | errors % |
| --- | ---: | ---: | ---: | ---: | ---: |
| go-gin | **185** | **53.89** | **56.86** | 60.01 | **0.00** |
| rust-axum | 184 | 53.98 | 57.01 | **58.97** | **0.00** |
| node-fastify | 178 | 56.06 | 64.13 | 79.74 | **0.00** |
| php-laravel | 144 | 69.20 | 102.15 | 124.49 | **0.00** |
| python-fastapi | 91 | 109.36 | 212.85 | 224.19 | **0.00** |

## Performance ranking

Reflects measured throughput (RPS) only, not the full weighted decision matrix.

| Stack | avg rank | scenarios |
| --- | ---: | ---: |
| go-gin | 1.40 | 5 |
| rust-axum | 1.60 | 5 |
| node-fastify | 3.40 | 5 |
| python-fastapi | 4.00 | 5 |
| php-laravel | 4.60 | 5 |

## Resource Consumption

Sampled via `docker stats` once per second across all scenarios (CPU% can
exceed 100% — it is summed across cores).

| Stack | CPU % avg | CPU % peak | Mem avg (MiB) | Mem peak (MiB) |
|-------|-----------|-----------|---------------|----------------|
| php-laravel | 256.7 | 398.3 | 139.0 | 140.5 |
| node-fastify | 86.4 | 122.0 | 103.2 | 272.3 |
| python-fastapi | 202.1 | 391.5 | 177.6 | 180.3 |
| go-gin | 138.7 | 386.2 | 11.9 | 15.1 |
| rust-axum | 120.8 | 393.9 | 10.6 | 13.0 |
