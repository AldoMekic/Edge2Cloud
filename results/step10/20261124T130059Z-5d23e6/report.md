# Edge2Cloud Step 10 Benchmark

Run ID: `20261124T130059Z-5d23e6`

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
| median_ms | 4.0252 | 1.1596 |
| mean_ms | 4.1622 | 1.211 |
| p95_ms | 5.1543 | 1.5276 |
| p99_ms | 5.1543 | 1.5276 |

### PDP concurrent workload

| Workers | RPS | p50 (ms) | p95 (ms) | Errors | Correct |
|---:|---:|---:|---:|---:|---:|
| 1 | 407.392 | 2.2758 | 2.9519 | 0 | 120/120 |
| 4 | 652.978 | 5.8269 | 7.9251 | 0 | 120/120 |
| 8 | 675.989 | 11.4581 | 15.2114 | 0 | 120/120 |

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
      "baseline_latency_ms": 5.690647,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 7.136459,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.250094,
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
      "baseline_latency_ms": 5.223516,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 12.441344,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.158573,
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
      "baseline_latency_ms": 5.294634,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 12.754172,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.328945,
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
      "baseline_latency_ms": 1.994335,
      "baseline_cache_hit": true,
      "ai_request_latency_ms": 14.064603,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.222767,
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
      "baseline_latency_ms": 4.744544,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 13.544762,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.643054,
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
- Client-to-denial observation: 12.000 ms
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
