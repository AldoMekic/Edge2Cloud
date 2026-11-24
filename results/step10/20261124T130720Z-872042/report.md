# Edge2Cloud Step 10 Benchmark

Run ID: `20261124T130720Z-872042`

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
| median_ms | 4.1084 | 1.1232 |
| mean_ms | 4.1128 | 1.1162 |
| p95_ms | 4.2803 | 1.1945 |
| p99_ms | 4.2803 | 1.1945 |

### PDP concurrent workload

| Workers | RPS | p50 (ms) | p95 (ms) | Errors | Correct |
|---:|---:|---:|---:|---:|---:|
| 1 | 415.649 | 2.3173 | 2.5284 | 0 | 120/120 |
| 4 | 631.422 | 6.3089 | 8.6274 | 0 | 120/120 |
| 8 | 684.142 | 11.4314 | 14.243 | 0 | 120/120 |

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
      "baseline_latency_ms": 2.526812,
      "baseline_cache_hit": true,
      "ai_request_latency_ms": 18.600417,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.555521,
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
      "baseline_latency_ms": 5.282813,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 12.379788,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.198026,
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
      "baseline_latency_ms": 4.823026,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 11.904853,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.174591,
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
      "baseline_latency_ms": 2.870711,
      "baseline_cache_hit": true,
      "ai_request_latency_ms": 13.11935,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.489453,
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
      "baseline_latency_ms": 4.944545,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 10.674775,
      "prefetch_status": "success",
      "prediction_confidence": 0.681419,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.396405,
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
- Client-to-denial observation: 12.206 ms
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
