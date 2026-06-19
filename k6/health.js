import http from 'k6/http';
import { check } from 'k6';

// Scenario 1 — Health Check: measures raw framework overhead.
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
    http_req_duration: ['p(95)<50', 'p(99)<100'],
  },
};

export default function () {
  const res = http.get(`${TARGET}/health`);
  check(res, {
    'status is 200': (r) => r.status === 200,
    'body is ok': (r) => r.json('status') === 'ok',
  });
}
