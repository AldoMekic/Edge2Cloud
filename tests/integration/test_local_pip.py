
import json
import os
import sys
import time
import urllib.request
import urllib.error

PIP_URL = os.getenv(
    "LOCAL_PIP_URL",
    "http://localhost:8003"
)

TEST_CASES = [
    ("user:operator-001", "can_start", True),
    ("user:viewer-001", "can_start", False),
    ("user:technician-001", "can_maintain", True),
]


def request_relationship(user, relation):
    payload = {
        "user": user,
        "relation": relation,
        "resource": "device:actuator-001"
    }

    request = urllib.request.Request(
        f"{PIP_URL}/resolve-relationship",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode())


def check(label, result, expected_allowed,
          expected_cache_hit):

    success = (
        type(result.get("allowed")) is bool
        and result["allowed"] == expected_allowed
        and result.get("cache_hit") is expected_cache_hit
        and result.get("cloud_fallback") is
            (not expected_cache_hit)
        and result.get("source") == "openfga"
    )

    status = "PASS" if success else "FAIL"

    print(
        f"{status:4} | {label:30} | "
        f"allowed={result.get('allowed')} | "
        f"cache_hit={result.get('cache_hit')} | "
        f"cloud_fallback={result.get('cloud_fallback')} | "
        f"latency={result.get('pip_latency_ms')} ms"
    )

    return success


def run_tests():
    passed = 0
    total = 0

    print("=" * 80)
    print("LOCAL PIP STAGE 1 / REDIS INTEGRATION TESTS")
    print("=" * 80)

    for user, relation, expected in TEST_CASES:

        # Test 1: Request with cache miss
        # The first run should use an empty cache.
        # The following test cases use distinct keys.
        first = request_relationship(user, relation)

        total += 1
        if check(
            f"{user}: first request",
            first, expected, False
        ):
            passed += 1

        # Test 2: Immediate cache hit
        second = request_relationship(user, relation)

        total += 1
        if check(
            f"{user}: repeated request",
            second, expected, True
        ):
            passed += 1

    # Test 3: TTL expiry
    print("\nWaiting 6 seconds for cache expiry...")
    time.sleep(6)

    user, relation, expected = TEST_CASES[0]

    expired = request_relationship(user, relation)

    total += 1
    if check(
        "Expired cache request",
        expired, expected, False
    ):
        passed += 1

    print("-" * 80)
    print(f"Results: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    try:
        success = run_tests()
        sys.exit(0 if success else 1)

    except Exception as error:
        print(f"TEST ERROR: {error}")
        sys.exit(1)
