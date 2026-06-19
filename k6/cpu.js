import http from 'k6/http';
import { check } from 'k6';

// Scenario 4 — CPU Intensive: chained SHA-256.
// ROUNDS controls how much CPU work per request (tune for your hardware).
const TARGET = __ENV.TARGET || 'http://go-gin:8000';
const ROUNDS = __ENV.ROUNDS || '50000';

export const options = {
  scenarios: {
    constant_load: {
      executor: 'constant-vus',
      vus: 20,
      duration: '30s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const res = http.get(`${TARGET}/cpu/${ROUNDS}`);
  check(res, {
    'status is 200': (r) => r.status === 200,
    'rounds echoed': (r) => r.json('rounds') === Number(ROUNDS),
    'hash is 64 hex': (r) => /^[0-9a-f]{64}$/.test(r.json('hash') || ''),
  });
}
