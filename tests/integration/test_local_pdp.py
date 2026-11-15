
"""Integration tests for Edge2Cloud Local PDP."""

import json
import os
import sys
import urllib.error
import urllib.request


PDP_URL = os.getenv(
    "LOCAL_PDP_URL",
    "http://127.0.0.1:8004"
)

RESOURCE = "device:actuator-001"

TEST_CASES = [
    (
        "Operator can start",
        "user:operator-001",
        "edge:start",
        "ALLOW",
        "RELATIONSHIP_TRUE"
    ),
    (
        "Viewer cannot start",
        "user:viewer-001",
        "edge:start",
        "DENY",
        "RELATIONSHIP_FALSE"
    ),
    (
        "Technician can maintain",
        "user:technician-001",
        "edge:maintain",
        "ALLOW",
        "RELATIONSHIP_TRUE"
    ),
    (
        "Viewer can read",
        "user:viewer-001",
        "edge:read",
        "ALLOW",
        "RELATIONSHIP_TRUE"
    ),
    (
        "Operator cannot maintain",
        "user:operator-001",
        "edge:maintain",
        "DENY",
        "RELATIONSHIP_FALSE"
    ),
    (
        "Explicitly prohibited action",
        "user:operator-001",
        "edge:delete",
        "DENY",
        "EXPLICIT_PROHIBITION"
    ),
    (
        "Undefined action",
        "user:operator-001",
        "edge:reset",
        "DENY",
        "NO_APPLICABLE_PERMISSION"
    )
]


def send_request(payload):
    request = urllib.request.Request(
        f"{PDP_URL}/evaluate",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=10
        ) as response:
            return response.status, json.load(response)

    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def run_tests():
    passed = 0
    total = 0

    print("=" * 76)
    print("EDGE2CLOUD LOCAL PDP INTEGRATION TESTS")
    print("=" * 76)

    for (
        name,
        user,
        action,
        expected_decision,
        expected_reason
    ) in TEST_CASES:

        total += 1

        status, result = send_request({
            "user": user,
            "resource": RESOURCE,
            "action": action
        })

        actual_decision = result.get("decision")
        actual_reason = result.get("reason")

        success = (
            status == 200
            and actual_decision == expected_decision
            and actual_reason == expected_reason
            and result.get("policy_version") == "v1"
        )

        if success:
            passed += 1

        print(
            f"{'PASS' if success else 'FAIL'} | "
            f"{name:30} | "
            f"Expected: {expected_decision:13} | "
            f"Actual: {actual_decision}"
        )

        if not success:
            print(f"  HTTP status: {status}")
            print(f"  Response: {result}")

    # Test 8: Unknown resource
    total += 1

    status, result = send_request({
        "user": "user:operator-001",
        "resource": "device:unknown",
        "action": "edge:start"
    })

    success = (
        status == 200
        and result.get("decision") == "DENY"
        and result.get("reason") == "NO_POLICY"
    )

    if success:
        passed += 1

    print(
        f"{'PASS' if success else 'FAIL'} | "
        "Unknown resource"
    )

    if not success:
        print(f"  HTTP status: {status}")
        print(f"  Response: {result}")

    # Test 9: Reject client-supplied evaluation clock
    total += 1

    status, result = send_request({
        "user": "user:operator-001",
        "resource": RESOURCE,
        "action": "edge:start",
        "now": "2000-01-01T00:00:00Z"
    })

    success = status == 400

    if success:
        passed += 1

    print(
        f"{'PASS' if success else 'FAIL'} | "
        "Reject client-supplied clock"
    )

    if not success:
        print(f"  HTTP status: {status}")
        print(f"  Response: {result}")

    print("-" * 76)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("RESULT: ALL LOCAL PDP TESTS PASSED")
    else:
        print("RESULT: LOCAL PDP TESTS FAILED")

    return passed == total


if __name__ == "__main__":
    try:
        success = run_tests()
        sys.exit(0 if success else 1)

    except Exception as error:
        print(f"TEST ERROR: {error}")
        sys.exit(1)
