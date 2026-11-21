# Edge2Cloud Step 10 Benchmark

Run ID: `20261121T153012Z-1de576`

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
| median_ms | 7.0558 | 1.1213 |
| mean_ms | 7.3655 | 1.1066 |
| p95_ms | 9.0894 | 1.1258 |
| p99_ms | 9.0894 | 1.1258 |

### PDP concurrent workload

| Workers | RPS | p50 (ms) | p95 (ms) | Errors | Correct |
|---:|---:|---:|---:|---:|---:|
| 1 | 438.244 | 2.1178 | 2.4709 | 0 | 40/40 |
| 4 | 623.582 | 6.2012 | 8.6764 | 0 | 40/40 |

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
      "baseline_latency_ms": 6.812001,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 13.666938,
      "prefetch_status": "success",
      "prediction_confidence": 0.789676,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.405056,
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
      "baseline_latency_ms": 4.563869,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 14.38696,
      "prefetch_status": "success",
      "prediction_confidence": 0.789676,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.586426,
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
- Client-to-denial observation: 14.072 ms
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
