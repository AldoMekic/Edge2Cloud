# Edge2Cloud Step 10 Benchmark

Run ID: `20261124T124229Z-b550dd`

## Experimental conditions

- Single host, local Docker Compose deployment
- OpenFGA and Redis run in containers
- Relationship cache TTL: 5 seconds
- Test relationship uses a temporary test user
- AI model trained on synthetic data

## Results

## Limitations

- This is a single-machine baseline, not a multi-edge experiment.
- Cache and prefetch samples are small and not randomized.
- Docker scheduling and background traffic influence results.
- The simulated user workload is deterministic.
- The AI model uses synthetic training data.
- Revocation measurements include API and observation delays.
- External OpenFGA mutations are not covered by the event gateway.
- A production PEP and authenticated control plane are not yet evaluated.

## Run error

Cache experiment failed: cold {'user': 'user:step9-bench-f08573886b', 'relation': 'can_read', 'resource': 'device:actuator-001', 'allowed': True, 'source': 'openfga', 'model_version': '01M707PQ3QC1S4EJ6H7F8J47WR', 'retrieved_at': 1795524155.2688622, 'cache_hit': True, 'cloud_fallback': False, 'cache_ttl_seconds': 0, 'cache_generation': 2, 'pip_latency_ms': 0.647}
