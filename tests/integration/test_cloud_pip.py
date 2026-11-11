
import json
import os
import sys
import urllib.request
import urllib.error

# Configuration
CLOUD_PIP_URL = os.getenv(
    "CLOUD_PIP_URL",
    "http://localhost:8002"
)

EXPECTED_MODEL_ID = os.getenv(
    "FGA_MODEL_ID",
    "01M707PQ3QC1S4EJ6H7F8J47WR"
)

RESOURCE = "device:actuator-001"

# Test cases
TESTS = [
    {
        "name": "Operator can start actuator",
        "user": "user:operator-001",
        "relation": "can_start",
        "expected": True
    },
    {
        "name": "Viewer cannot start actuator",
        "user": "user:viewer-001",
        "relation": "can_start",
        "expected": False
    },
    {
        "name": "Technician can maintain actuator",
        "user": "user:technician-001",
        "relation": "can_maintain",
        "expected": True
    }
]


def check_relationship(test):
    """Send a relationship request to Cloud PIP Stage 2."""

    url = f"{CLOUD_PIP_URL}/check-relationship"

    payload = {
        "user": test["user"],
        "relation": test["relation"],
        "resource": RESOURCE
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def run_tests():
    passed = 0
    failed = 0

    print("=" * 65)
    print("CLOUD PIP STAGE 2 - OPENFGA INTEGRATION TESTS")
    print("=" * 65)
    print(f"Endpoint: {CLOUD_PIP_URL}")
    print(f"Model ID: {EXPECTED_MODEL_ID}")
    print()

    for index, test in enumerate(TESTS, start=1):
        print(f"TEST {index}: {test['name']}")

        try:
            result = check_relationship(test)

            expected_fields = {
                "source": "openfga",
                "user": test["user"],
                "relation": test["relation"],
                "resource": RESOURCE,
                "allowed": test["expected"],
                "model_version": EXPECTED_MODEL_ID
            }

            mismatches = {
                key: {
                    "expected": expected,
                    "actual": result.get(key)
                }
                for key, expected in expected_fields.items()
                if type(result.get(key)) is not type(expected)
                or result.get(key) != expected
            }

            if not mismatches:
                print("  Status: PASS")
                print(f"  Allowed: {result['allowed']}")
                passed += 1
            else:
                print("  Status: FAIL")
                print("  Unexpected response fields:")
                print(json.dumps(mismatches, indent=2))
                failed += 1

        except urllib.error.HTTPError as error:
            print(f"  Status: ERROR (HTTP {error.code})")
            print(
                "  Response:",
                error.read().decode("utf-8", errors="replace")
            )
            failed += 1

        except Exception as error:
            print(f"  Status: ERROR ({error})")
            failed += 1

        print("-" * 65)

    print()
    print("FINAL RESULTS")
    print(f"Passed: {passed}/{len(TESTS)}")
    print(f"Failed: {failed}/{len(TESTS)}")

    if failed == 0:
        print("RESULT: ALL CLOUD PIP TESTS PASSED")
    else:
        print("RESULT: CLOUD PIP INTEGRATION NEEDS ATTENTION")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
