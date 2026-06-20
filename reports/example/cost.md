# Phase 4 Cost Model

> Modeled from measured throughput and peak resource usage — an efficiency estimate, NOT a cloud bill. Representative scenario: database.

Provisioning assumes one instance is sized for measured peak CPU/memory. Target throughput: 1,000 rps over 730 hours/month.

### AWS Fargate

| Stack | RPS | vCPU | Mem (GB) | $/hr (1 inst) | $/1M req | instances @ 1,000 rps | $/mo @ target |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| node-fastify | 16,138 | 1.22 | 0.27 | $0.0506 | **$0.0009** | 1 | $36.91 |
| go-gin | 31,353 | 3.86 | 0.01 | $0.1564 | $0.0014 | 1 | $114.17 |
| rust-axum | 27,535 | 3.94 | 0.01 | $0.1595 | $0.0016 | 1 | $116.44 |
| python-fastapi | 10,985 | 3.92 | 0.18 | $0.1593 | $0.0040 | 1 | $116.26 |
| php-laravel | 4,348 | 3.98 | 0.14 | $0.1618 | $0.0103 | 1 | $118.14 |

### GCP Cloud Run

| Stack | RPS | vCPU | Mem (GB) | $/hr (1 inst) | $/1M req | instances @ 1,000 rps | $/mo @ target |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| node-fastify | 16,138 | 1.22 | 0.27 | $0.1078 | **$0.0019** | 1 | $78.69 |
| go-gin | 31,353 | 3.86 | 0.01 | $0.3338 | $0.0030 | 1 | $243.68 |
| rust-axum | 27,535 | 3.94 | 0.01 | $0.3404 | $0.0034 | 1 | $248.52 |
| python-fastapi | 10,985 | 3.92 | 0.18 | $0.3398 | $0.0086 | 1 | $248.08 |
| php-laravel | 4,348 | 3.98 | 0.14 | $0.3454 | $0.0221 | 1 | $252.12 |

### Generic VM

| Stack | RPS | vCPU | Mem (GB) | $/hr (1 inst) | $/1M req | instances @ 1,000 rps | $/mo @ target |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| node-fastify | 16,138 | 1.22 | 0.27 | $0.0257 | **$0.0004** | 1 | $18.78 |
| go-gin | 31,353 | 3.86 | 0.01 | $0.0773 | $0.0007 | 1 | $56.44 |
| rust-axum | 27,535 | 3.94 | 0.01 | $0.0788 | $0.0008 | 1 | $57.56 |
| python-fastapi | 10,985 | 3.92 | 0.18 | $0.0792 | $0.0020 | 1 | $57.80 |
| php-laravel | 4,348 | 3.98 | 0.14 | $0.0803 | $0.0051 | 1 | $58.65 |

**Takeaway:** under AWS Fargate, **node-fastify** is the most cost-efficient stack at $0.0009 per 1M requests.
