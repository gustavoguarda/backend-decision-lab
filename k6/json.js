import http from 'k6/http';
import { check } from 'k6';

// Scenario 2 — JSON Serialization: static payload, no DB.
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
    http_req_duration: ['p(95)<75', 'p(99)<150'],
  },
};

export default function () {
  const res = http.get(`${TARGET}/serialize`);
  check(res, {
    'status is 200': (r) => r.status === 200,
    'id is 123': (r) => r.json('id') === 123,
    'name matches': (r) => r.json('name') === 'John Doe',
  });
}
