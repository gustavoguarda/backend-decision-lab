# Horizontal Scaling — go-gin

Throughput as replica count increases (Docker DNS round-robin). Scaling factor = RPS(n) / RPS(base); efficiency = factor / (n / base_replicas).

| Replicas | RPS | p95 (ms) | Scaling factor | Efficiency |
|---------:|----:|---------:|---------------:|-----------:|
| 1 | 69,538 | 2.01 | 1.00x | 100% |
| 2 | 64,590 | 2.3 | 0.93x | 46% |
| 4 | 55,604 | 2.65 | 0.80x | 20% |

> Efficiency near 100% means throughput scales linearly with replicas; lower values indicate a shared bottleneck (often the single Postgres or host CPU).
