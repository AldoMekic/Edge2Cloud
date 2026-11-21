# Edge2Cloud Step 10 Benchmark

Run ID: `20261121T153140Z-fbbd9e`

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
| median_ms | 7.0802 | 1.0554 |
| mean_ms | 6.9364 | 1.1105 |
| p95_ms | 9.4404 | 1.3035 |
| p99_ms | 9.4404 | 1.3035 |

### PDP concurrent workload

| Workers | RPS | p50 (ms) | p95 (ms) | Errors | Correct |
|---:|---:|---:|---:|---:|---:|
| 1 | 452.735 | 2.1192 | 2.34 | 0 | 120/120 |
| 4 | 657.929 | 5.9306 | 8.1738 | 0 | 120/120 |
| 8 | 663.127 | 10.8169 | 24.5581 | 0 | 120/120 |

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
      "baseline_latency_ms": 6.433517,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 14.054106,
      "prefetch_status": "success",
      "prediction_confidence": 0.789676,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.539707,
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
      "baseline_latency_ms": 8.686823,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 13.96236,
      "prefetch_status": "success",
      "prediction_confidence": 0.789676,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.506749,
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
      "baseline_latency_ms": 6.399681,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 17.876859,
      "prefetch_status": "success",
      "prediction_confidence": 0.789676,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.196486,
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
      "baseline_latency_ms": 6.273189,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 12.094527,
      "prefetch_status": "success",
      "prediction_confidence": 0.789676,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.351319,
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
      "baseline_latency_ms": 7.256757,
      "baseline_cache_hit": false,
      "ai_request_latency_ms": 12.115556,
      "prefetch_status": "success",
      "prediction_confidence": 0.789676,
      "predicted_relation_matched": true,
      "followup_latency_ms": 1.426107,
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
- Client-to-denial observation: 11.754 ms
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
