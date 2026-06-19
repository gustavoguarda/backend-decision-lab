# Implementation Contract

Every implementation under `implementations/` MUST satisfy this contract exactly so
that benchmarks are comparable. A stack that deviates is not measuring the same thing.

## Runtime

- The service listens on HTTP port **8000** inside the container.
- It is fully containerized: a single `Dockerfile` builds and runs it. No host toolchain.
- It reads its database configuration from environment variables (never hardcoded):

  | Variable      | Value in compose      |
  |---------------|-----------------------|
  | `DB_HOST`     | `postgres`            |
  | `DB_PORT`     | `5432`                |
  | `DB_NAME`     | `benchmark`           |
  | `DB_USER`     | `benchmark`           |
  | `DB_PASSWORD` | `benchmark`           |
  | `APP_PORT`    | `8000`                |
  | `UPSTREAM_URL`| `http://upstream:8080`|

- Postgres may not be ready instantly. The service should tolerate a brief startup
  delay (retry the initial connection or use a connection pool that connects lazily).

## Endpoints

### `GET /health` — Scenario 1 (framework overhead)
Status `200`, JSON body:
```json
{ "status": "ok" }
```

### `GET /serialize` — Scenario 2 (JSON serialization, no DB)
Status `200`, static JSON body (exact values):
```json
{ "id": 123, "name": "John Doe", "email": "john@example.com" }
```
`id` MUST be a JSON number (not a string).

### `GET /cpu/{rounds}` — Scenario 4 (CPU-intensive)
Chained SHA-256: start from the fixed seed string `"backend-decision-lab"`, then hash
the result `rounds` times (each round hashes the *raw 32 bytes* of the previous digest).
Return the final digest as lowercase hex.

- `rounds` is a positive integer. Clamp to a max of `10000000` to bound abuse.
- Status `200`:
  ```json
  { "rounds": 100000, "hash": "<64-char lowercase hex>" }
  ```
- `rounds` is a JSON number. Invalid/zero `rounds` → `404 {"error":"not found"}`.

Reference algorithm (so every stack produces the SAME hash for a given `rounds`):
```
h = sha256_bytes(utf8("backend-decision-lab"))   # round 1
for _ in range(rounds - 1): h = sha256_bytes(h)  # rounds 2..N
return lowercase_hex(h)
```
So `rounds=1` is a single `sha256(seed)`. Each subsequent round hashes the raw
32-byte digest of the previous round (NOT its hex string).

### `GET /aggregate` — Scenario 5 (concurrent external requests)
Fire **10 concurrent** GET requests to the upstream mock service, each to
`${UPSTREAM_URL}/delay/0.05` (a 50 ms delayed response), wait for all to finish,
then return. With real async/concurrency total time ≈ one delay (~50 ms); a
sequential implementation takes ~500 ms — that contrast is the measurement.

- `UPSTREAM_URL` comes from env (compose sets `http://upstream:8080`).
- All 10 must run concurrently (not sequentially).
- Status `200`:
  ```json
  { "requests": 10, "succeeded": 10, "took_ms": 53 }
  ```
  `requests`/`succeeded` are JSON numbers; `took_ms` is the wall-clock of the fan-out.

### `GET /users/{id}` — Scenario 3 (database access)
Runs `SELECT id, name, email, created_at FROM users WHERE id = $1` against Postgres.

- Found → status `200`:
  ```json
  { "id": 123, "name": "John Doe", "email": "john@example.com", "created_at": "2026-06-19T12:00:00Z" }
  ```
  `id` is a JSON number; `created_at` is an ISO-8601 string.
- Not found → status `404`:
  ```json
  { "error": "not found" }
  ```
- Use a parameterized query (no string interpolation) and a connection pool.

## Database schema

Seeded by `infrastructure/postgres/init.sql` (10,000 rows; id `123` = John Doe):
```sql
CREATE TABLE users (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## Host port map (for reference; set in docker-compose.yml)

| Service          | Host port |
|------------------|-----------|
| php-laravel      | 8001      |
| node-fastify     | 8002      |
| python-fastapi   | 8003      |
| go-gin           | 8004      |
| rust-axum        | 8005      |
