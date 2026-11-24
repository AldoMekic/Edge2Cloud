# Edge2Cloud Step 10 Benchmark

Run ID: `20261124T125532Z-202b1a`

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
| median_ms | 3.8503 | 1.0833 |
| mean_ms | 3.9004 | 1.0931 |
| p95_ms | 4.1515 | 1.1773 |
| p99_ms | 4.1515 | 1.1773 |

### PDP concurrent workload

| Workers | RPS | p50 (ms) | p95 (ms) | Errors | Correct |
|---:|---:|---:|---:|---:|---:|
| 1 | 437.472 | 2.1669 | 2.3098 | 0 | 120/120 |
| 4 | 654.451 | 5.7412 | 8.2312 | 0 | 120/120 |
| 8 | 697.977 | 10.9174 | 14.8226 | 0 | 120/120 |

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
      "baseline_latency_ms": 7.426102,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 13.912416,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.302507,
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
      "baseline_latency_ms": 8.048656,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 13.614502,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.630134,
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
      "baseline_latency_ms": 7.934341,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 10.644601,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.422225,
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
      "baseline_latency_ms": 5.546431,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 12.779637,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.234298,
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
      "baseline_latency_ms": 5.242547,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 16.367503,
      "prefetch_status": "success",
      "prediction_confidence": 0.649849,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.299725,
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
- Client-to-denial observation: 11.598 ms
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
