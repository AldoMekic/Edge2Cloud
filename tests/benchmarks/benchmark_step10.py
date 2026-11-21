
"""Edge2Cloud Step 10 scientific benchmark runner.

Requires the verified Step 9 Docker Compose stack.

Measures:
1. Redis relationship evidence: cold and warm lookup
2. Concurrent PDP throughput and response latency
3. AI prefetching followed by evidence reuse
4. Revocation visibility and Kafka event observation

Outputs CSV, JSON metadata and Markdown report.

Uses only the Python standard library.
"""

import argparse
import concurrent.futures
import csv
import json
import math
import platform
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

PIP_URL = "http://127.0.0.1:8003"
PDP_URL = "http://127.0.0.1:8004"
DT_URL = "http://127.0.0.1:8005"
AI_URL = "http://127.0.0.1:8006"
CHANGE_URL = "http://127.0.0.1:8007"

RESOURCE = "device:actuator-001"
RELATION = "can_read"
ACTION = "edge:read"

RUN_ID = datetime.now(timezone.utc).strftime(
    "%Y%m%dT%H%M%SZ"
) + "-" + uuid.uuid4().hex[:6]

USER = f"user:step9-bench-{uuid.uuid4().hex[:10]}"

OUTPUT = ROOT / "results" / "step10" / RUN_ID
OUTPUT.mkdir(parents=True, exist_ok=True)

ROWS = []
PHASE_RESULTS = {}
GRANTED = False

COLUMNS = [
    "run_id",
    "timestamp_utc",
    "scenario",
    "cohort",
    "request_index",
    "concurrency",
    "http_status",
    "expected_decision",
    "actual_decision",
    "correct",
    "latency_ms",
    "cache_hit",
    "cloud_fallback",
    "cache_generation",
    "prefetch_status",
    "relation",
    "notes"
]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def request(url, payload=None, timeout=12):
    body = (
        json.dumps(payload).encode("utf-8")
        if payload is not None
        else None
    )

    req = urllib.request.Request(
        url,
        data=body,
        headers=(
            {"Content-Type": "application/json"}
            if body is not None
            else {}
        ),
        method="POST" if body is not None else "GET"
    )

    start = time.perf_counter_ns()

    try:
        with urllib.request.urlopen(
            req, timeout=timeout
        ) as response:
            status = response.status
            raw = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        raw = error.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        elapsed = (
            time.perf_counter_ns() - start
        ) / 1_000_000

        return 0, {"error": str(exc)}, elapsed

    elapsed = (
        time.perf_counter_ns() - start
    ) / 1_000_000

    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError):
        data = {"error": "Non-JSON response"}

    return status, data, elapsed


def record(
    scenario,
    cohort,
    index,
    concurrency,
    status,
    response,
    latency,
    expected=None,
    notes=""
):
    actual = response.get("decision")

    if expected is None:
        correct = ""
    else:
        correct = (
            status == 200 and actual == expected
        )

    row = {
        "run_id": RUN_ID,
        "timestamp_utc": utc_now(),
        "scenario": scenario,
        "cohort": cohort,
        "request_index": index,
        "concurrency": concurrency,
        "http_status": status,
        "expected_decision": expected or "",
        "actual_decision": actual or "",
        "correct": correct,
        "latency_ms": round(latency, 4),
        "cache_hit": response.get("cache_hit", ""),
        "cloud_fallback": response.get(
            "cloud_fallback", ""
        ),
        "cache_generation": response.get(
            "cache_generation", ""
        ),
        "prefetch_status": response.get(
            "prefetch_status", ""
        ),
        "relation": response.get("relation", ""),
        "notes": notes
    }

    ROWS.append(row)
    return row


def percentile(values, percent):
    if not values:
        return None

    ordered = sorted(values)

    index = max(
        0,
        math.ceil(percent / 100 * len(ordered)) - 1
    )

    return ordered[index]


def summarize(rows):
    values = [
        r["latency_ms"]
        for r in rows
        if r["http_status"] == 200
    ]

    errors = sum(
        r["http_status"] != 200
        for r in rows
    )

    correctness = [
        r["correct"]
        for r in rows
        if isinstance(r["correct"], bool)
    ]

    return {
        "requests": len(rows),
        "http_errors": errors,
        "correct_decisions": sum(correctness),
        "evaluated_decisions": len(correctness),
        "mean_ms": (
            round(statistics.mean(values), 4)
            if values else None
        ),
        "median_ms": (
            round(statistics.median(values), 4)
            if values else None
        ),
        "p95_ms": (
            round(percentile(values, 95), 4)
            if values else None
        ),
        "p99_ms": (
            round(percentile(values, 99), 4)
            if values else None
        ),
        "min_ms": min(values) if values else None,
        "max_ms": max(values) if values else None
    }


def redis_value(key):
    process = subprocess.run(
        [
            "docker", "compose", "exec", "-T",
            "redis", "redis-cli",
            "--raw", "GET", key
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10
    )

    if process.returncode:
        raise RuntimeError(process.stderr)

    value = process.stdout.strip()
    return None if value in ("", "(nil)") else value


def redis_exists(key):
    process = subprocess.run(
        [
            "docker", "compose", "exec", "-T",
            "redis", "redis-cli",
            "--raw", "EXISTS", key
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10
    )

    if process.returncode:
        raise RuntimeError(process.stderr)

    return process.stdout.strip() == "1"


def mutate(operation):
    return request(
        f"{CHANGE_URL}/mutate",
        {
            "operation": operation,
            "user": USER,
            "relation": "viewer",
            "resource": RESOURCE
        }
    )


def pip_payload(user=USER, relation=RELATION):
    return {
        "user": user,
        "relation": relation,
        "resource": RESOURCE
    }


def pdp_payload(user=USER, action=ACTION):
    return {
        "user": user,
        "resource": RESOURCE,
        "action": action
    }


def verify_services():
    print("\n[1] Verifying services")

    for name, url in (
        ("PIP", PIP_URL),
        ("PDP", PDP_URL),
        ("Digital Twin", DT_URL),
        ("AI Prefetch", AI_URL),
        ("Change API", CHANGE_URL)
    ):
        status, response, _ = request(
            f"{url}/health"
        )

        if status != 200:
            raise RuntimeError(
                f"{name} not ready: {response}"
            )

        print(f"  PASS {name}")

    status, observation, _ = request(
        f"{DT_URL}/devices/actuator-001"
    )

    if (
        status != 200
        or observation.get("freshness") != "FRESH"
    ):
        raise RuntimeError(
            "Digital Twin telemetry is not fresh"
        )

    return observation


def grant_test_identity():
    global GRANTED

    status, response, latency = mutate("grant")

    if (
        status != 200
        or response.get("status") != "applied"
    ):
        raise RuntimeError(
            f"Test user grant failed: {response}"
        )

    GRANTED = True

    PHASE_RESULTS["grant"] = {
        "latency_ms": latency,
        "generation": response.get(
            "local_generation"
        )
    }

    print(f"  Test identity granted: {USER}")


def experiment_cache(pairs, ttl):
    print("\n[2] Cold versus warm PIP cache")

    results = []

    for cycle in range(1, pairs + 1):
        # Allow the five-second relationship TTL to expire.
        time.sleep(ttl + 0.3)

        for cohort in ("cold", "warm"):
            status, response, latency = request(
                f"{PIP_URL}/resolve-relationship",
                pip_payload()
            )

            row = record(
                "pip_cache",
                cohort,
                cycle,
                1,
                status,
                response,
                latency,
                notes=f"TTL={ttl}s"
            )

            results.append(row)

            if (
                status != 200
                or response.get("allowed") is not True
                or response.get("cache_hit") is not (
                    cohort == "warm"
                )
            ):
                raise RuntimeError(
                    f"Cache experiment failed: "
                    f"{cohort} {response}"
                )

    cold = [
        row for row in results
        if row["cohort"] == "cold"
    ]

    warm = [
        row for row in results
        if row["cohort"] == "warm"
    ]

    PHASE_RESULTS["cache"] = {
        "cold": summarize(cold),
        "warm": summarize(warm),
        "warm_cache_hit_rate": (
            sum(r["cache_hit"] is True for r in warm)
            / len(warm)
        )
    }

    print(
        "  Cold median:",
        PHASE_RESULTS["cache"]["cold"]["median_ms"],
        "ms"
    )
    print(
        "  Warm median:",
        PHASE_RESULTS["cache"]["warm"]["median_ms"],
        "ms"
    )


def one_pdp_request(index):
    # Deterministic 75% allowed, 25% denied mix.
    if index % 4 == 0:
        action = "edge:start"
        expected = "DENY"
    else:
        action = "edge:read"
        expected = "ALLOW"

    status, response, elapsed = request(
        f"{PDP_URL}/evaluate",
        pdp_payload(action=action)
    )

    return index, expected, status, response, elapsed


def experiment_load(workers_list, requests_per_level):
    print("\n[3] Concurrent PDP workload")

    phase = {}

    for workers in workers_list:
        start = time.perf_counter()

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=workers
        ) as pool:
            futures = [
                pool.submit(one_pdp_request, index)
                for index in range(requests_per_level)
            ]

            observations = [
                future.result()
                for future in concurrent.futures.as_completed(
                    futures
                )
            ]

        elapsed = time.perf_counter() - start

        current_rows = []

        for index, expected, status, response, latency in observations:
            current_rows.append(
                record(
                    "pdp_load",
                    f"workers_{workers}",
                    index,
                    workers,
                    status,
                    response,
                    latency,
                    expected=expected
                )
            )

        summary = summarize(current_rows)

        summary["wall_seconds"] = round(elapsed, 4)
        summary["throughput_rps"] = round(
            len(current_rows) / elapsed, 3
        )

        phase[str(workers)] = summary

        print(
            f"  Workers={workers} "
            f"RPS={summary['throughput_rps']} "
            f"p95={summary['p95_ms']} ms "
            f"errors={summary['http_errors']} "
            f"correct={summary['correct_decisions']}/"
            f"{summary['evaluated_decisions']}"
        )

    PHASE_RESULTS["load"] = phase


def experiment_prefetch(rounds, ttl):
    print("\n[4] AI-assisted predictive prefetch")

    phase = []

    # First retrieve the predicted relation. This call
    # may itself prefetch evidence, so it is excluded
    # from the latency comparison.
    status, initial, _ = request(
        f"{AI_URL}/observe",
        {
            "user": "user:operator-001",
            "resource": RESOURCE,
            "action": "edge:read",
            "decision": "ALLOW"
        }
    )

    if (
        status != 200
        or initial.get("predicted_relation") not in (
            "can_read", "can_start", "can_maintain"
        )
    ):
        PHASE_RESULTS["prefetch"] = {
            "status": "unavailable",
            "response": initial
        }
        return

    relation = initial["predicted_relation"]

    for cycle in range(1, rounds + 1):
        # Baseline: ordinary cold PIP lookup.
        time.sleep(ttl + 0.3)

        cold_status, cold_data, cold_ms = request(
            f"{PIP_URL}/resolve-relationship",
            pip_payload(
                user="user:operator-001",
                relation=relation
            )
        )

        record(
            "prefetch",
            "baseline_cold",
            cycle,
            1,
            cold_status,
            cold_data,
            cold_ms,
            notes=relation
        )

        # Expire baseline cache before prefetching.
        time.sleep(ttl + 0.3)

        ai_status, ai_data, ai_ms = request(
            f"{AI_URL}/observe",
            {
                "user": "user:operator-001",
                "resource": RESOURCE,
                "action": "edge:read",
                "decision": "ALLOW"
            }
        )

        record(
            "prefetch",
            "ai_observation",
            cycle,
            1,
            ai_status,
            ai_data,
            ai_ms,
            notes=ai_data.get(
                "predicted_relation", ""
            )
        )

        follow_status, follow_data, follow_ms = request(
            f"{PIP_URL}/resolve-relationship",
            pip_payload(
                user="user:operator-001",
                relation=relation
            )
        )

        record(
            "prefetch",
            "after_prefetch",
            cycle,
            1,
            follow_status,
            follow_data,
            follow_ms,
            notes=relation
        )

        matched = (
            ai_data.get("prefetched_relation") == relation
        )

        phase.append({
            "round": cycle,
            "relation": relation,
            "baseline_latency_ms": cold_ms,
            "baseline_cache_hit": cold_data.get(
                "cache_hit"
            ),
            "ai_request_latency_ms": ai_ms,
            "prefetch_status": ai_data.get(
                "prefetch_status"
            ),
            "prediction_confidence": ai_data.get(
                "confidence"
            ),
            "predicted_relation_matched": matched,
            "followup_latency_ms": follow_ms,
            "followup_cache_hit": follow_data.get(
                "cache_hit"
            ),
            "authoritative_result_matches": (
                cold_data.get("allowed")
                == follow_data.get("allowed")
            ),
            "http_statuses": [
                cold_status,
                ai_status,
                follow_status
            ]
        })

        print(
            f"  Round {cycle}: "
            f"baseline={cold_ms:.3f}ms, "
            f"followup={follow_ms:.3f}ms, "
            f"prefetch={ai_data.get('prefetch_status')}, "
            f"cache_hit={follow_data.get('cache_hit')}"
        )

    PHASE_RESULTS["prefetch"] = {
        "status": "completed",
        "fixed_relation": relation,
        "rounds": phase,
        "note": (
            "Controlled evidence-reuse demonstration, "
            "not a real-workload prefetch hit-rate estimate"
        )
    }


def experiment_revocation():
    global GRANTED

    print("\n[5] Revocation and Kafka visibility")

    # Warm an ALLOW result immediately before mutation.
    status, before, _ = request(
        f"{PIP_URL}/resolve-relationship",
        pip_payload()
    )

    if status != 200 or before.get("allowed") is not True:
        raise RuntimeError(
            "Expected granted relationship before revocation"
        )

    status, before_pdp, _ = request(
        f"{PDP_URL}/evaluate",
        pdp_payload()
    )

    if (
        status != 200
        or before_pdp.get("decision") != "ALLOW"
    ):
        raise RuntimeError(
            "PDP was not allowing the test user before revocation"
        )

    epoch_before = redis_value(
        f"auth:epoch:{RESOURCE}"
    )

    t0 = time.perf_counter()
    mutation_status, mutation, mutation_ms = mutate(
        "revoke"
    )
    t_response = time.perf_counter()

    if (
        mutation_status != 200
        or mutation.get("status") != "applied"
    ):
        # The API can fail AFTER OpenFGA has changed.
        # Avoid treating failure as proof of no mutation.
        raise RuntimeError(
            f"Revocation not confirmed: {mutation}"
        )

    GRANTED = False

    status, after_pip, pip_ms = request(
        f"{PIP_URL}/resolve-relationship",
        pip_payload()
    )

    record(
        "revocation",
        "post_revoke_pip",
        1,
        1,
        status,
        after_pip,
        pip_ms,
        notes="expected allowed=false"
    )

    status_pdp, after_pdp, pdp_ms = request(
        f"{PDP_URL}/evaluate",
        pdp_payload()
    )

    record(
        "revocation",
        "post_revoke_pdp",
        1,
        1,
        status_pdp,
        after_pdp,
        pdp_ms,
        expected="DENY"
    )

    t_decision = time.perf_counter()

    if (
        status != 200
        or after_pip.get("allowed") is not False
        or status_pdp != 200
        or after_pdp.get("decision") != "DENY"
    ):
        raise RuntimeError(
            "Authorization revocation visibility failed"
        )

    event_id = mutation["kafka_event_id"]

    kafka_seen = False
    deadline = time.monotonic() + 15

    while time.monotonic() < deadline:
        if redis_exists(f"auth:event:{event_id}"):
            kafka_seen = True
            break

        time.sleep(0.1)

    t_event_observed = time.perf_counter()

    result = {
        "mutation_api_latency_ms": mutation_ms,
        "api_elapsed_from_start_ms": (
            t_response - t0
        ) * 1000,
        "deny_observed_from_start_ms": (
            t_decision - t0
        ) * 1000,
        "kafka_event_seen": kafka_seen,
        "kafka_observed_from_start_ms": (
            (t_event_observed - t0) * 1000
            if kafka_seen else None
        ),
        "epoch_before": epoch_before,
        "epoch_after": redis_value(
            f"auth:epoch:{RESOURCE}"
        ),
        "post_revoke_pip_allowed": after_pip.get(
            "allowed"
        ),
        "post_revoke_pip_cache_hit": after_pip.get(
            "cache_hit"
        ),
        "post_revoke_pdp_decision": after_pdp.get(
            "decision"
        ),
        "event_id": event_id,
        "note": (
            "Times include control-plane/API and "
            "client observation overhead. Kafka "
            "propagation is not measured independently."
        )
    }

    PHASE_RESULTS["revocation"] = result

    print(
        "  PDP decision:", after_pdp.get("decision")
    )
    print(
        "  Client-to-denial observation:",
        round(result["deny_observed_from_start_ms"], 3),
        "ms"
    )
    print("  Kafka event observed:", kafka_seen)

    if not kafka_seen:
        raise RuntimeError(
            "Kafka event not observed within 15 seconds"
        )


def capture_environment():
    command = subprocess.run(
        ["docker", "compose", "ps"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=20
    )

    status, ai_metrics, _ = request(
        f"{AI_URL}/metrics"
    )

    return {
        "run_id": RUN_ID,
        "timestamp_utc": utc_now(),
        "test_user": USER,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "docker_compose_ps": command.stdout,
        "ai_metrics": (
            ai_metrics if status == 200 else None
        ),
        "resource": RESOURCE,
        "cache_ttl_assumed_seconds": 5,
        "note": "Single-host local Docker experiment"
    }


def save_results(metadata, error=None):
    OUTPUT.mkdir(parents=True, exist_ok=True)

    with (OUTPUT / "observations.csv").open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file, fieldnames=COLUMNS
        )
        writer.writeheader()
        writer.writerows(ROWS)

    results = {
        "metadata": metadata,
        "phases": PHASE_RESULTS,
        "error": error
    }

    (OUTPUT / "results.json").write_text(
        json.dumps(results, indent=2, default=str),
        encoding="utf-8"
    )

    report = [
        "# Edge2Cloud Step 10 Benchmark",
        "",
        f"Run ID: `{RUN_ID}`",
        "",
        "## Experimental conditions",
        "",
        "- Single host, local Docker Compose deployment",
        "- OpenFGA and Redis run in containers",
        "- Relationship cache TTL: 5 seconds",
        "- Test relationship uses a temporary test user",
        "- AI model trained on synthetic data",
        "",
        "## Results",
        ""
    ]

    cache_results = PHASE_RESULTS.get("cache", {})

    if cache_results:
        report += [
            "### Cold and warm cache",
            "",
            "| Metric | Cold | Warm |",
            "|---|---:|---:|",
        ]

        for key in (
            "median_ms",
            "mean_ms",
            "p95_ms",
            "p99_ms"
        ):
            report.append(
                f"| {key} | "
                f"{cache_results['cold'].get(key)} | "
                f"{cache_results['warm'].get(key)} |"
            )

        report.append("")

    load = PHASE_RESULTS.get("load", {})

    if load:
        report += [
            "### PDP concurrent workload",
            "",
            "| Workers | RPS | p50 (ms) | p95 (ms) | Errors | Correct |",
            "|---:|---:|---:|---:|---:|---:|"
        ]

        for workers, result in load.items():
            report.append(
                f"| {workers} | "
                f"{result['throughput_rps']} | "
                f"{result['median_ms']} | "
                f"{result['p95_ms']} | "
                f"{result['http_errors']} | "
                f"{result['correct_decisions']}/"
                f"{result['evaluated_decisions']} |"
            )

        report.append("")

    prefetch = PHASE_RESULTS.get("prefetch", {})

    if prefetch:
        report += [
            "### AI prefetch",
            "",
            "Controlled follow-up evidence reuse; "
            "not a natural prefetch hit-rate measurement.",
            "",
            "```json",
            json.dumps(prefetch, indent=2),
            "```",
            ""
        ]

    revocation = PHASE_RESULTS.get("revocation")

    if revocation:
        report += [
            "### Revocation",
            "",
            f"- Post-revoke PDP decision: "
            f"{revocation['post_revoke_pdp_decision']}",
            f"- Client-to-denial observation: "
            f"{revocation['deny_observed_from_start_ms']:.3f} ms",
            f"- Kafka event observed: "
            f"{revocation['kafka_event_seen']}",
            "",
            "This is not a pure Kafka propagation latency.",
            ""
        ]

    report += [
        "## Limitations",
        "",
        "- This is a single-machine baseline, not a multi-edge experiment.",
        "- Cache and prefetch samples are small and not randomized.",
        "- Docker scheduling and background traffic influence results.",
        "- The simulated user workload is deterministic.",
        "- The AI model uses synthetic training data.",
        "- Revocation measurements include API and observation delays.",
        "- External OpenFGA mutations are not covered by the event gateway.",
        "- A production PEP and authenticated control plane are not yet evaluated.",
        ""
    ]

    if error:
        report += [
            "## Run error",
            "",
            str(error),
            ""
        ]

    (OUTPUT / "report.md").write_text(
        "\n".join(report),
        encoding="utf-8"
    )


def main():
    global GRANTED

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--cache-pairs",
        type=int,
        default=5
    )

    parser.add_argument(
        "--requests",
        type=int,
        default=120
    )

    parser.add_argument(
        "--workers",
        default="1,4,8"
    )

    parser.add_argument(
        "--prefetch-rounds",
        type=int,
        default=3
    )

    parser.add_argument(
        "--cache-ttl",
        type=float,
        default=5.0
    )

    args = parser.parse_args()

    workers = [
        int(value)
        for value in args.workers.split(",")
    ]

    if (
        not 1 <= args.cache_pairs <= 100
        or not 1 <= args.requests <= 10000
        or not 0 <= args.prefetch_rounds <= 100
        or not 1 <= args.cache_ttl <= 3600
        or not workers
        or any(not 1 <= w <= 32 for w in workers)
    ):
        parser.error("Invalid benchmark parameters")

    print("=" * 72)
    print("EDGE2CLOUD SCIENTIFIC BENCHMARK — STEP 10")
    print("=" * 72)
    print("Run:", RUN_ID)
    print("Output:", OUTPUT)

    metadata = {
        "run_id": RUN_ID,
        "arguments": vars(args)
    }

    error = None

    try:
        dt = verify_services()
        metadata.update(capture_environment())
        metadata["initial_digital_twin"] = dt

        grant_test_identity()

        experiment_cache(
            args.cache_pairs, args.cache_ttl
        )

        experiment_load(
            workers, args.requests
        )

        if args.prefetch_rounds:
            experiment_prefetch(
                args.prefetch_rounds,
                args.cache_ttl
            )

        experiment_revocation()

    except Exception as exc:
        error = str(exc)
        print("BENCHMARK ERROR:", error)

    finally:
        if GRANTED:
            print("\nCleaning up test relationship...")

            status, response, _ = mutate("revoke")

            print(
                "Cleanup:",
                status,
                response.get("status", response)
            )

            if status == 200:
                GRANTED = False
            else:
                error = (
                    (error + "; " if error else "")
                    + "TEST USER CLEANUP NOT CONFIRMED"
                )

        try:
            save_results(metadata, error)
        except Exception as exc:
            print("Could not save results:", exc)
            return 1

    print("\nFiles saved under:", OUTPUT)
    print("  observations.csv")
    print("  results.json")
    print("  report.md")

    if error:
        print("RESULT: INCOMPLETE")
        return 1

    print("RESULT: BENCHMARK FINISHED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
