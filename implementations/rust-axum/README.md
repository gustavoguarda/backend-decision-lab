# rust-axum

Axum 0.7 implementation for the multi-stack backend benchmark lab.

## Stack

- **Rust** (stable, `rust:1-bookworm` build image)
- **Axum 0.7** with `tokio` multi-thread runtime (`axum::serve` + `tokio::net::TcpListener`)
- **sqlx 0.8** with `runtime-tokio-rustls` + `postgres` + `chrono` features, using a `PgPool`
- **chrono** `DateTime<Utc>` for `TIMESTAMPTZ`, serialized to RFC3339 / ISO-8601

## Endpoints

| Method | Path         | Behavior |
|--------|--------------|----------|
| GET    | `/health`    | `200 {"status":"ok"}` |
| GET    | `/serialize` | `200 {"id":123,"name":"John Doe","email":"john@example.com"}` (id is a JSON number) |
| GET    | `/users/:id` | Parameterized `SELECT ... WHERE id = $1`. Found -> `200` with `created_at` as ISO-8601 string; `RowNotFound` -> `404 {"error":"not found"}` |

## Configuration

All DB config comes from env vars only; the connection URL is built at runtime:

- `DB_HOST` (default `postgres`)
- `DB_PORT` (default `5432`)
- `DB_NAME` (default `benchmark`)
- `DB_USER` (default `benchmark`)
- `DB_PASSWORD` (default `benchmark`)
- `APP_PORT` (default `8000`)

The pool is created with a 5s acquire timeout and a ~30s startup retry loop, so a
brief Postgres startup delay does not crash the app.

## Build / run

```sh
docker build -t rust-axum .
docker run -p 8000:8000 \
  -e DB_HOST=postgres -e DB_PORT=5432 \
  -e DB_NAME=benchmark -e DB_USER=benchmark -e DB_PASSWORD=benchmark \
  rust-axum
```

Multi-stage Dockerfile: `rust:1-bookworm` compiles `--release`, `debian:bookworm-slim`
runs the binary on port 8000.

## Notes / caveats

- **Runtime query mode only.** Uses `sqlx::query(...).bind(...)` with runtime row access
  (`row.get(...)`), NOT the compile-time-checked `query!`/`query_as!` macros. No live DB
  and no `DATABASE_URL` is required at build time.
- TLS is via `rustls` (pure Rust), so no `libpq` / `libssl` is needed in the runtime image;
  `ca-certificates` is included for trust roots.
- The DB connection to Postgres is plaintext (no `sslmode` in the URL); fine for the
  in-cluster benchmark setup.
- `Path<i32>` is used for `/users/:id`; a non-integer path segment yields a `400` from the
  extractor (acceptable per contract). A valid-but-missing id yields the `404` JSON body.
- The schema is pre-seeded externally; this app never creates or migrates tables.
