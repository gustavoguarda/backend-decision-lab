# php-laravel

Laravel 11 (PHP 8.3) implementation of the backend benchmark contract.

## Serving

- **Base image:** `dunglas/frankenphp:1-php8.3` — FrankenPHP, a production-grade
  PHP application server built on Caddy.
- **Runtime:** [Laravel Octane](https://laravel.com/docs/octane) on the
  FrankenPHP runtime, started in **worker mode**
  (`php artisan octane:start --server=frankenphp`). The framework is booted once
  per worker and kept resident, so requests skip the cold bootstrap cost — the
  high-throughput, idiomatic way to serve Laravel.
- Listens on `0.0.0.0:8000` inside the container.

## How it's built

The Dockerfile does the heavy lifting (network is required at **build time**):

1. `composer create-project laravel/laravel:^11.0 .` pulls the framework skeleton
   and all dependencies from Packagist.
2. `composer require laravel/octane` + `octane:install --server=frankenphp`.
3. The few files we author are overlaid on top:
   - `routes/web.php` — registers `/health`, `/serialize`, `/users/{id}` at the
     root path (no `/api` prefix).
   - `app/Http/Controllers/BenchmarkController.php` — the three handlers.
   - `config/database.php` — `pgsql` connection reading the contract's env vars
     (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) with
     `PDO::ATTR_PERSISTENT => true` for connection reuse.
4. Routes are cached and OPcache + JIT are tuned for the benchmark.

## Endpoints

| Method | Path           | Behavior                                                                 |
| ------ | -------------- | ------------------------------------------------------------------------ |
| GET    | `/health`      | `200 {"status":"ok"}`                                                     |
| GET    | `/serialize`   | `200 {"id":123,"name":"John Doe","email":"john@example.com"}`            |
| GET    | `/users/{id}`  | Parameterized `SELECT id, name, email, created_at FROM users WHERE id=?` |

- `id` is cast to `int` so it serializes as a JSON **number**, not a string.
- `created_at` is normalized to an ISO-8601 string via Carbon.
- Missing user → `404 {"error":"not found"}`.

## Notes / caveats

- **Build-time network:** Composer must reach Packagist during `docker build`.
  No framework code is committed; only the authored overlay files are.
- **Config is deliberately NOT cached** (`config:cache` is not run) so the
  `DB_*` env vars injected by `docker compose` at container start are read live.
  Routes *are* cached.
- The `users` table is pre-seeded externally (10k rows). No migrations are run;
  the app only reads.
- Postgres readiness: the connection is lazy — Laravel connects on the first
  query, so a brief Postgres startup delay is tolerated (only `/users/{id}`
  touches the DB; `/health` and `/serialize` never do).
- Persistent PDO connections are reused across requests within each resident
  Octane worker.
