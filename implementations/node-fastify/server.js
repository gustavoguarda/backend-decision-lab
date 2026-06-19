import Fastify from 'fastify';
import pg from 'pg';
import crypto from 'crypto';

const { Pool } = pg;

const pool = new Pool({
  host: process.env.DB_HOST || 'postgres',
  port: parseInt(process.env.DB_PORT || '5432', 10),
  database: process.env.DB_NAME || 'benchmark',
  user: process.env.DB_USER || 'benchmark',
  password: process.env.DB_PASSWORD || 'benchmark',
});

// Don't crash the process on idle-client errors (e.g. DB briefly down).
pool.on('error', (err) => {
  app.log.error({ err }, 'unexpected idle pg client error');
});

const app = Fastify({ logger: true });

app.get('/health', async () => {
  return { status: 'ok' };
});

app.get('/serialize', async () => {
  return { id: 123, name: 'John Doe', email: 'john@example.com' };
});

app.get('/users/:id', async (request, reply) => {
  const raw = request.params.id;

  // Strict integer parse: reject anything that isn't a clean integer.
  if (!/^-?\d+$/.test(raw)) {
    reply.code(404);
    return { error: 'not found' };
  }
  const id = Number.parseInt(raw, 10);
  if (!Number.isSafeInteger(id)) {
    reply.code(404);
    return { error: 'not found' };
  }

  const result = await pool.query(
    'SELECT id, name, email, created_at FROM users WHERE id = $1',
    [id]
  );

  if (result.rowCount === 0) {
    reply.code(404);
    return { error: 'not found' };
  }

  const row = result.rows[0];
  return {
    id: row.id,
    name: row.name,
    email: row.email,
    // pg returns a JS Date for TIMESTAMPTZ; toISOString gives ISO-8601.
    created_at: row.created_at instanceof Date
      ? row.created_at.toISOString()
      : row.created_at,
  };
});

app.get('/cpu/:rounds', async (request, reply) => {
  const raw = request.params.rounds;

  // Strict integer parse: reject anything that isn't a clean positive integer.
  if (!/^\d+$/.test(raw)) {
    reply.code(404);
    return { error: 'not found' };
  }
  let rounds = Number.parseInt(raw, 10);
  if (!Number.isSafeInteger(rounds) || rounds <= 0) {
    reply.code(404);
    return { error: 'not found' };
  }
  if (rounds > 10000000) {
    rounds = 10000000;
  }

  // Chained SHA-256 over raw 32-byte digests (must match other stacks bit-for-bit).
  let h = crypto.createHash('sha256').update('backend-decision-lab', 'utf8').digest();
  for (let i = 1; i < rounds; i += 1) {
    h = crypto.createHash('sha256').update(h).digest();
  }

  return { rounds, hash: h.toString('hex') };
});

app.get('/aggregate', async () => {
  const upstream = process.env.UPSTREAM_URL;
  const url = `${upstream}/delay/0.05`;

  const start = process.hrtime.bigint();

  const results = await Promise.all(
    Array.from({ length: 10 }, () =>
      fetch(url)
        .then((res) => res.status === 200)
        .catch(() => false)
    )
  );

  const took_ms = Number((process.hrtime.bigint() - start) / 1000000n);
  const succeeded = results.filter(Boolean).length;

  return { requests: 10, succeeded, took_ms };
});

const port = parseInt(process.env.APP_PORT || '8000', 10);

try {
  await app.listen({ host: '0.0.0.0', port });
} catch (err) {
  app.log.error(err);
  process.exit(1);
}

const shutdown = async () => {
  try {
    await app.close();
    await pool.end();
  } finally {
    process.exit(0);
  }
};
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
