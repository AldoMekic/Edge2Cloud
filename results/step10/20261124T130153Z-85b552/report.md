# Edge2Cloud Step 10 Benchmark

Run ID: `20261124T130153Z-85b552`

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
| median_ms | 4.1615 | 1.1191 |
| mean_ms | 4.1393 | 1.1461 |
| p95_ms | 4.3754 | 1.3472 |
| p99_ms | 4.3754 | 1.3472 |

### PDP concurrent workload

| Workers | RPS | p50 (ms) | p95 (ms) | Errors | Correct |
|---:|---:|---:|---:|---:|---:|
| 1 | 423.154 | 2.263 | 2.4874 | 0 | 120/120 |
| 4 | 602.245 | 6.7655 | 8.4937 | 0 | 120/120 |
| 8 | 677.873 | 11.2133 | 15.3037 | 0 | 120/120 |

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
      "baseline_latency_ms": 5.28635,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 14.64641,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.363543,
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
      "baseline_latency_ms": 2.748922,
      "baseline_cache_hit": true,
      "ai_request_latency_ms": 16.090459,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.347857,
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
      "baseline_latency_ms": 4.592609,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 15.567122,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.538199,
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
      "baseline_latency_ms": 5.890877,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 9.081887,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.288362,
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
      "baseline_latency_ms": 8.276066,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 14.817609,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.40523,
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
- Client-to-denial observation: 13.201 ms
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
