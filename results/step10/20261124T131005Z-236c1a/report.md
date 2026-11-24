# Edge2Cloud Step 10 Benchmark

Run ID: `20261124T131005Z-236c1a`

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
| median_ms | 3.8869 | 1.0832 |
| mean_ms | 3.8721 | 1.071 |
| p95_ms | 4.015 | 1.145 |
| p99_ms | 4.015 | 1.145 |

### PDP concurrent workload

| Workers | RPS | p50 (ms) | p95 (ms) | Errors | Correct |
|---:|---:|---:|---:|---:|---:|
| 1 | 421.743 | 2.139 | 2.3111 | 0 | 120/120 |
| 4 | 633.284 | 6.2194 | 8.062 | 0 | 120/120 |
| 8 | 695.224 | 11.0484 | 15.3588 | 0 | 120/120 |

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
      "baseline_latency_ms": 6.261747,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 20.902334,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.579062,
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
      "baseline_latency_ms": 5.445869,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 10.234368,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.340532,
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
      "baseline_latency_ms": 5.492114,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 12.328747,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.196654,
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
      "baseline_latency_ms": 8.468922,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 16.867347,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.254211,
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
      "baseline_latency_ms": 3.242848,
      "baseline_cache_hit": true,
      "ai_request_latency_ms": 14.958834,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.443124,
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
- Client-to-denial observation: 11.791 ms
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
