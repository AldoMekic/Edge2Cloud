# Edge2Cloud Step 10 Benchmark

Run ID: `20261124T130626Z-644a5d`

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
| median_ms | 4.177 | 1.1235 |
| mean_ms | 4.1307 | 1.1268 |
| p95_ms | 4.3038 | 1.2176 |
| p99_ms | 4.3038 | 1.2176 |

### PDP concurrent workload

| Workers | RPS | p50 (ms) | p95 (ms) | Errors | Correct |
|---:|---:|---:|---:|---:|---:|
| 1 | 420.414 | 2.2679 | 2.517 | 0 | 120/120 |
| 4 | 633.104 | 6.0218 | 8.6811 | 0 | 120/120 |
| 8 | 666.198 | 11.4205 | 16.2352 | 0 | 120/120 |

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
      "baseline_latency_ms": 2.389102,
      "baseline_cache_hit": true,
      "ai_request_latency_ms": 10.40744,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.310749,
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
      "baseline_latency_ms": 5.116089,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 12.490296,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.19946,
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
      "baseline_latency_ms": 4.61181,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 8.126987,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.063569,
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
      "baseline_latency_ms": 4.685473,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 10.046035,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.4901,
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
      "baseline_latency_ms": 4.757971,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 11.277812,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.283955,
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
- Client-to-denial observation: 12.504 ms
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
