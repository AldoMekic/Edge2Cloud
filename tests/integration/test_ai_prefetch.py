
"""Edge2Cloud AI prefetch integration tests."""

import json
import sys
import time
import urllib.error
import urllib.request


AI_URL = "http://127.0.0.1:8006"
PIP_URL = "http://127.0.0.1:8003"
PDP_URL = "http://127.0.0.1:8004"

RESOURCE = "device:actuator-001"

RELATIONS = {
    "edge:read": "can_read",
    "edge:start": "can_start",
    "edge:maintain": "can_maintain"
}

passed = 0
total = 0


def http_request(url, payload=None):
    if payload is None:
        request = urllib.request.Request(
            url,
            method="GET"
        )
    else:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

    try:
        with urllib.request.urlopen(
            request, timeout=12
        ) as response:
            return response.status, json.load(response)

    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def check(name, condition, detail=""):
    global total, passed

    total += 1

    if condition:
        passed += 1

    print(
        f"{'PASS' if condition else 'FAIL'} | "
        f"{name}"
        + (f" | {detail}" if detail else "")
    )


def get_metrics():
    status, response = http_request(
        f"{AI_URL}/metrics"
    )

    if status != 200:
        raise RuntimeError("Could not retrieve AI metrics")

    return response["metrics"]


def run_tests():
    print("=" * 75)
    print("EDGE2CLOUD AI PREFETCH INTEGRATION TESTS")
    print("=" * 75)

    # Test 1: Model is loaded.
    status, health = http_request(
        f"{AI_URL}/health"
    )

    check(
        "AI model loaded",
        status == 200
        and health.get("model_loaded") is True
    )

    # Test 2: Produce a real model prediction
    # and prefetch a relationship.
    status, result = http_request(
        f"{AI_URL}/observe",
        {
            "user": "user:operator-001",
            "resource": RESOURCE,
            "action": "edge:read",
            "decision": "ALLOW"
        }
    )

    predicted_action = result.get("predicted_action")
    predicted_relation = result.get("predicted_relation")

    check(
        "AI prediction generated",
        status == 200
        and predicted_action in RELATIONS
        and predicted_relation == RELATIONS.get(
            predicted_action
        )
        and 0 <= result.get("confidence", -1) <= 1,
        str(predicted_action)
    )

    check(
        "Authoritative prefetch completed",
        result.get("prefetch_status") == "success"
        and result.get("evidence_source") == "openfga"
        and isinstance(
            result.get("authoritative_allowed"),
            bool
        ),
        result.get("prefetch_status", "")
    )

    # Test 4: Check whether Local PIP can
    # reuse the prefetched Redis evidence.
    if result.get("prefetch_status") == "success":
        pip_status, evidence = http_request(
            f"{PIP_URL}/resolve-relationship",
            {
                "user": "user:operator-001",
                "resource": RESOURCE,
                "relation": predicted_relation
            }
        )

        check(
            "Prefetched evidence available in Redis",
            pip_status == 200
            and evidence.get("cache_hit") is True
            and evidence.get("cloud_fallback") is False
            and evidence.get("allowed") ==
                result.get("authoritative_allowed")
        )

    else:
        check(
            "Prefetched evidence available in Redis",
            False,
            "Prefetch was not successful"
        )

    # Test 5: A denied observation must not
    # cause speculative prefetching.
    status, denied = http_request(
        f"{AI_URL}/observe",
        {
            "user": "user:viewer-001",
            "resource": RESOURCE,
            "action": "edge:start",
            "decision": "DENY"
        }
    )

    check(
        "Denied observation does not prefetch",
        status == 200
        and denied.get("prefetch_status") ==
            "skipped_denied"
    )

    # Test 6: An invalid event is rejected.
    status, invalid = http_request(
        f"{AI_URL}/observe",
        {
            "user": "user:operator-001",
            "resource": RESOURCE,
            "action": "edge:read",
            "decision": "ALLOW",
            "allowed": True
        }
    )

    check(
        "Unexpected observation fields rejected",
        status == 400
    )

    # Test 7: The authoritative PDP still
    # denies a viewer permission to start.
    status, decision = http_request(
        f"{PDP_URL}/evaluate",
        {
            "user": "user:viewer-001",
            "resource": RESOURCE,
            "action": "edge:start"
        }
    )

    check(
        "AI does not override PDP denial",
        status == 200
        and decision.get("decision") == "DENY"
    )

    # Test 8: A PDP observation is automatically
    # passed to the AI service.
    before = get_metrics()["observations"]

    status, read_result = http_request(
        f"{PDP_URL}/evaluate",
        {
            "user": "user:operator-001",
            "resource": RESOURCE,
            "action": "edge:read"
        }
    )

    updated = False

    if status == 200 and read_result.get("decision") == "ALLOW":
        for _ in range(40):
            if get_metrics()["observations"] > before:
                updated = True
                break

            time.sleep(0.2)

    check(
        "PDP sends observations asynchronously",
        updated
    )

    # Test 9: Metrics are being collected.
    metrics = get_metrics()

    check(
        "Prefetch metrics recorded",
        metrics.get("predictions", 0) >= 1
        and metrics.get("prefetch_successes", 0) >= 1
        and metrics.get("prefetch_attempts", 0) >= 1
    )

    print("-" * 75)
    print(f"Results: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    try:
        success = run_tests()
        sys.exit(0 if success else 1)

    except Exception as exc:
        print(f"TEST ERROR: {exc}")
        sys.exit(1)
