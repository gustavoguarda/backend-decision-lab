import http from 'k6/http';
import { check } from 'k6';

// Scenario 3 — Database Access: indexed lookup against Postgres.
const TARGET = __ENV.TARGET || 'http://go-gin:8000';

export const options = {
  scenarios: {
    constant_load: {
      executor: 'constant-vus',
      vus: 50,
      duration: '30s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<150', 'p(99)<300'],
  },
  // The random user id below would otherwise produce a unique `url` label per
  // request, exploding Prometheus series cardinality (enough to OOM it). Drop the
  // per-URL `url` tag; the constant `name` tag on the request (below) collapses
  // every lookup into a single metric series.
  systemTags: ['proto', 'status', 'method', 'name', 'check', 'error', 'error_code', 'scenario', 'expected_response'],
};

export default function () {
  // Vary the id across the seeded range to avoid trivial caching effects.
  const id = Math.floor(Math.random() * 10000) + 1;
  const res = http.get(`${TARGET}/users/${id}`, { tags: { name: 'users' } });
  check(res, {
    'status is 200': (r) => r.status === 200,
    'id matches': (r) => r.json('id') === id,
    'has email': (r) => typeof r.json('email') === 'string',
  });
}
