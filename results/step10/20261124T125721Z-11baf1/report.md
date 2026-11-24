# Edge2Cloud Step 10 Benchmark

Run ID: `20261124T125721Z-11baf1`

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
| median_ms | 3.8815 | 1.0496 |
| mean_ms | 3.9292 | 1.0676 |
| p95_ms | 4.0572 | 1.2011 |
| p99_ms | 4.0572 | 1.2011 |

### PDP concurrent workload

| Workers | RPS | p50 (ms) | p95 (ms) | Errors | Correct |
|---:|---:|---:|---:|---:|---:|
| 1 | 433.134 | 2.1749 | 2.4287 | 0 | 120/120 |
| 4 | 646.361 | 5.9209 | 8.3143 | 0 | 120/120 |
| 8 | 714.475 | 10.8135 | 14.9752 | 0 | 120/120 |

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
      "baseline_latency_ms": 9.729903,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 18.415542,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.430724,
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
      "baseline_latency_ms": 6.323942,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 11.146455,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.375416,
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
      "baseline_latency_ms": 5.816507,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 11.990379,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.166076,
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
      "baseline_latency_ms": 7.368062,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 12.140662,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.268967,
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
      "baseline_latency_ms": 5.445596,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 15.273304,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.474439,
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
- Client-to-denial observation: 12.437 ms
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
