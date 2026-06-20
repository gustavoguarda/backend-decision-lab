# Deployment footprint

_Generated 2026-06-20T13:23:21. Image size = registry/pull cost; cold start = container boot until GET /health returns 200 (image already local). Smallest image and fastest cold start in **bold**._

| Stack | Image size (MB) | Cold start (ms) |
| --- | ---: | ---: |
| go-gin | **4.6** | 170 |
| rust-axum | 33.6 | **142** |
| node-fastify | 53.8 | 388 |
| python-fastapi | 62.8 | 600 |
| php-laravel | 261.1 | 833 |
