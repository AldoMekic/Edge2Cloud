# Edge2Cloud Step 10 Benchmark

Run ID: `20261124T125626Z-aa888b`

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
| median_ms | 3.9558 | 1.0588 |
| mean_ms | 4.1318 | 1.0671 |
| p95_ms | 5.4637 | 1.1339 |
| p99_ms | 5.4637 | 1.1339 |

### PDP concurrent workload

| Workers | RPS | p50 (ms) | p95 (ms) | Errors | Correct |
|---:|---:|---:|---:|---:|---:|
| 1 | 435.489 | 2.1747 | 2.443 | 0 | 120/120 |
| 4 | 634.322 | 6.0898 | 8.557 | 0 | 120/120 |
| 8 | 720.302 | 10.7568 | 13.9734 | 0 | 120/120 |

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
      "baseline_latency_ms": 6.669175,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 11.644279,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.442914,
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
      "baseline_latency_ms": 5.896067,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 9.831934,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.577069,
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
      "baseline_latency_ms": 6.964092,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 12.358913,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.574591,
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
      "baseline_latency_ms": 5.21635,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 10.352207,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.529492,
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
      "baseline_latency_ms": 2.403009,
      "baseline_cache_hit": true,
      "ai_request_latency_ms": 12.649093,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.400244,
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
- Client-to-denial observation: 12.085 ms
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
