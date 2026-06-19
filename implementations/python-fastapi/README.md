# Python + FastAPI implementation

FastAPI app served by uvicorn, using asyncpg with a connection pool for Postgres.

## Details

- **Base image:** `python:3.12-slim`
- **Server:** uvicorn with **4 workers** (`--workers 4`), HTTP port `8000`.
- **DB driver:** asyncpg (async, connection pool, `min_size=2`, `max_size=10`).
- **JSON:** `ORJSONResponse` set as the default response class for speed and correct
  numeric serialization (`id` is emitted as a JSON number, not a string).

## Config (env vars only)

`DB_HOST=postgres`, `DB_PORT=5432`, `DB_NAME=benchmark`, `DB_USER=benchmark`,
`DB_PASSWORD=benchmark`, `APP_PORT=8000`. Sensible defaults are baked in.

## Endpoints

- `GET /health` -> `{"status":"ok"}`
- `GET /serialize` -> `{"id":123,"name":"John Doe","email":"john@example.com"}`
- `GET /users/{id}` -> user row, or `404 {"error":"not found"}`

## Startup / resilience

The asyncpg pool is created in FastAPI's `lifespan` startup with a ~30s retry loop, so
the app tolerates Postgres being briefly unavailable at boot rather than crashing.

## Caveats

- The DB schema and 10k seed rows are provisioned externally; this app does not create them.
- Each uvicorn worker is a separate process with its own asyncpg pool. Effective
  connection count = `workers * max_size` (here up to `4 * 10 = 40`); ensure Postgres
  `max_connections` accommodates this.
- `APP_PORT` is exposed as an env var per the contract but the listen port is hardcoded
  to `8000` in the `CMD` to keep the benchmark contract fixed.
- `created_at` is serialized via `.isoformat()`; with `TIMESTAMPTZ` it includes the UTC offset.
