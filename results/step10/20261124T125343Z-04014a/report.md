# Edge2Cloud Step 10 Benchmark

Run ID: `20261124T125343Z-04014a`

## Experimental conditions

- Single host, local Docker Compose deployment
- OpenFGA and Redis run in containers
- Relationship cache TTL: 5 seconds
- Test relationship uses a temporary test user
- AI model trained on synthetic data

## Results

### Cold and warm cache

| Metric | Cold | Warm |
|---|---:|---:|
| median_ms | 3.9249 | 1.0758 |
| mean_ms | 3.9642 | 1.1123 |
| p95_ms | 4.5274 | 1.3309 |
| p99_ms | 4.5274 | 1.3309 |

### PDP concurrent workload

| Workers | RPS | p50 (ms) | p95 (ms) | Errors | Correct |
|---:|---:|---:|---:|---:|---:|
| 1 | 444.734 | 2.1597 | 2.3059 | 0 | 120/120 |
| 4 | 616.139 | 6.548 | 8.417 | 0 | 120/120 |
| 8 | 602.521 | 11.2345 | 38.0241 | 0 | 120/120 |

### AI prefetch

Controlled follow-up evidence reuse; not a natural prefetch hit-rate measurement.

```json
{
  "status": "completed",
  "fixed_relation": "can_start",
  "rounds": [
    {
      "round": 1,
      "relation": "can_start",
      "baseline_latency_ms": 3.149409,
      "baseline_cache_hit": true,
      "ai_request_latency_ms": 13.383527,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.404272,
      "followup_cache_hit": true,
      "authoritative_result_matches": true,
      "http_statuses": [
        200,
        200,
        200
      ]
    },
    {
      "round": 2,
      "relation": "can_start",
      "baseline_latency_ms": 8.808248,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 14.395254,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.383038,
      "followup_cache_hit": true,
      "authoritative_result_matches": true,
      "http_statuses": [
        200,
        200,
        200
      ]
    },
    {
      "round": 3,
      "relation": "can_start",
      "baseline_latency_ms": 4.818439,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 14.38903,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.423199,
      "followup_cache_hit": true,
      "authoritative_result_matches": true,
      "http_statuses": [
        200,
        200,
        200
      ]
    },
    {
      "round": 4,
      "relation": "can_start",
      "baseline_latency_ms": 1.755675,
      "baseline_cache_hit": true,
      "ai_request_latency_ms": 12.777665,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.223606,
      "followup_cache_hit": true,
      "authoritative_result_matches": true,
      "http_statuses": [
        200,
        200,
        200
      ]
    },
    {
      "round": 5,
      "relation": "can_start",
      "baseline_latency_ms": 6.676775,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 16.204766,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.464155,
      "followup_cache_hit": true,
      "authoritative_result_matches": true,
      "http_statuses": [
        200,
        200,
        200
      ]
    }
  ],
  "note": "Controlled evidence-reuse demonstration, not a real-workload prefetch hit-rate estimate"
}
```

### Revocation

- Post-revoke PDP decision: DENY
- Client-to-denial observation: 12.905 ms
- Kafka event observed: True

This is not a pure Kafka propagation latency.

## Limitations

- This is a single-machine baseline, not a multi-edge experiment.
- Cache and prefetch samples are small and not randomized.
- Docker scheduling and background traffic influence results.
- The simulated user workload is deterministic.
- The AI model uses synthetic training data.
- Revocation measurements include API and observation delays.
- External OpenFGA mutations are not covered by the event gateway.
- A production PEP and authenticated control plane are not yet evaluated.
