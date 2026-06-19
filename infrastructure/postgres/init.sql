-- Shared schema and seed data for every implementation.
-- Runs automatically on first container start (docker-entrypoint-initdb.d).

CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Deterministic seed: 10,000 users so the DB benchmark hits a real index lookup.
INSERT INTO users (id, name, email, created_at)
SELECT
    g,
    'User ' || g,
    'user' || g || '@example.com',
    now() - (g || ' minutes')::interval
FROM generate_series(1, 10000) AS g
ON CONFLICT (id) DO NOTHING;

-- Guarantee the canonical benchmark row exists exactly as the spec expects.
INSERT INTO users (id, name, email)
VALUES (123, 'John Doe', 'john@example.com')
ON CONFLICT (id) DO UPDATE
    SET name = EXCLUDED.name,
        email = EXCLUDED.email;
