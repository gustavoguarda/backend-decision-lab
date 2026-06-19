# go-gin

A Gin (Go 1.22) implementation of the backend benchmark contract.

## Approach

- **Framework:** [Gin](https://github.com/gin-gonic/gin) in release mode (`gin.SetMode(gin.ReleaseMode)`), listening on `:8000`.
- **Database:** [pgx v5](https://github.com/jackc/pgx/v5) with a `pgxpool` connection pool. The DSN is built entirely from env vars (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`).
- **Startup resilience:** `pgxpool.New` does not connect eagerly, so a `Ping` retry loop runs at startup for up to ~30s. This tolerates Postgres not being ready the instant the container boots.
- **Image:** multi-stage Dockerfile. The build stage (`golang:1.22-alpine`) compiles a static, CGO-free binary; the final stage runs it on `gcr.io/distroless/static:nonroot` for a tiny, rootless image.

## Endpoints

| Method | Path         | Behavior                                                                                  |
|--------|--------------|-------------------------------------------------------------------------------------------|
| GET    | `/health`    | `200 {"status":"ok"}`                                                                      |
| GET    | `/serialize` | `200 {"id":123,"name":"John Doe","email":"john@example.com"}` (`id` is a JSON number)      |
| GET    | `/users/:id` | Parameterized lookup. Non-integer id or no row -> `404 {"error":"not found"}`.             |

For `/users/:id`, `created_at` is scanned into a `time.Time` struct field, which Go's `encoding/json` marshals to an RFC3339 string automatically.

## Caveats

- `go.sum` is intentionally omitted; the Dockerfile runs `go mod download && go mod tidy` in the build stage to generate it. This requires network access during the image build to resolve the pinned module versions.
- Versions are pinned in `go.mod` (`gin v1.10.0`, `pgx/v5 v5.6.0`). `go mod tidy` may add transitive dependencies to the module graph at build time.
- The schema and seed data (10k rows, id 123 = John Doe) are provisioned externally; this app never creates or seeds tables.
