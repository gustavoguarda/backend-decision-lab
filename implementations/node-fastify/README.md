# node-fastify

Fastify (v5) + `pg` implementation for the backend benchmark lab.

## Stack

- **Base image:** `node:20-alpine` (single-stage build + run)
- **Runtime:** Node.js 20 LTS, ESM
- **Web framework:** Fastify 5.3.2
- **DB driver:** `pg` 8.13.1 using a lazy `pg.Pool`

## Endpoints

| Method | Path         | Behavior                                                           |
|--------|--------------|--------------------------------------------------------------------|
| GET    | `/health`    | `200 {"status":"ok"}`                                              |
| GET    | `/serialize` | `200 {"id":123,"name":"John Doe","email":"john@example.com"}`      |
| GET    | `/users/:id` | `200` user row, `404 {"error":"not found"}` if missing/invalid id |

## Configuration (env vars)

| Var           | Default     |
|---------------|-------------|
| `DB_HOST`     | `postgres`  |
| `DB_PORT`     | `5432`      |
| `DB_NAME`     | `benchmark` |
| `DB_USER`     | `benchmark` |
| `DB_PASSWORD` | `benchmark` |
| `APP_PORT`    | `8000`      |

Listens on `0.0.0.0:8000` inside the container.

## Build & run

```sh
docker build -t node-fastify .
docker run --rm -p 8000:8000 \
  -e DB_HOST=postgres -e DB_PORT=5432 \
  -e DB_NAME=benchmark -e DB_USER=benchmark -e DB_PASSWORD=benchmark \
  node-fastify
```

## Notes / caveats

- **Lazy DB connection:** `pg.Pool` connects on first query, so the app boots
  even if Postgres is briefly unavailable. An idle-client error handler on the
  pool prevents process crashes from dropped connections.
- **`id` types:** `pg` returns INTEGER columns as JS numbers, so `id`
  serializes as a JSON number with no extra coercion.
- **`created_at`:** `pg` returns `TIMESTAMPTZ` as a JS `Date`; we call
  `.toISOString()` to emit a stable ISO-8601 string.
- **`:id` parsing:** validated with a strict integer regex plus a safe-integer
  check; any non-integer (or out-of-range) value returns `404`, never a 500.
- **No lockfile committed:** the Dockerfile uses `npm install --omit=dev`
  (not `npm ci`), per the contract. Exact transitive versions are resolved at
  build time; the two direct deps are pinned in `package.json`.
- **DB query errors** (e.g. Postgres down at request time) surface as Fastify's
  default `500` response.
```
