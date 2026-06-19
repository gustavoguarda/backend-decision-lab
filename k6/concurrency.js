import http from 'k6/http';
import { check } from 'k6';

// Scenario 5 — Concurrent External Requests: fan out 10 concurrent upstream calls.
// Each upstream call has a ~50 ms delay; true async ≈ 50 ms, sequential ≈ 500 ms.
const TARGET = __ENV.TARGET || 'http://go-gin:8000';

export const options = {
  scenarios: {
    // Each iteration fans out to 10 upstream calls, so VUs amplify 10x against
    // the single mock upstream. 10 VUs = ~100 concurrent upstream calls, enough
    // load to compare async efficiency without saturating the mock itself.
    constant_load: {
      executor: 'constant-vus',
      vus: 10,
      duration: '30s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    // True concurrency keeps p95 near one upstream delay (~50ms), not the sum
    // of ten (~500ms). Ceiling allows headroom for scheduling under load.
    http_req_duration: ['p(95)<250'],
  },
};

export default function () {
  const res = http.get(`${TARGET}/aggregate`);
  check(res, {
    'status is 200': (r) => r.status === 200,
    'all 10 requested': (r) => r.json('requests') === 10,
    'all succeeded': (r) => r.json('succeeded') === 10,
  });
}
