
"""Edge2Cloud Step 9 Kafka invalidation integration tests."""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid


AUTH_URL = "http://127.0.0.1:8007"
PIP_URL = "http://127.0.0.1:8003"
PDP_URL = "http://127.0.0.1:8004"
DT_URL = "http://127.0.0.1:8005"

RESOURCE = "device:actuator-001"
USER = f"user:step9-{uuid.uuid4().hex[:12]}"

passed = 0
total = 0
relationship_granted = False


def http_json(url, payload=None):
    data = (
        json.dumps(payload).encode("utf-8")
        if payload is not None
        else None
    )

    request = urllib.request.Request(
        url,
        data=data,
        headers=(
            {"Content-Type": "application/json"}
            if data else {}
        ),
        method="POST" if data else "GET"
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=12
        ) as response:
            return response.status, json.load(response)

    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def redis_get(key):
    result = subprocess.run(
        [
            "docker", "compose", "exec", "-T",
            "redis", "redis-cli", "--raw", "GET", key
        ],
        capture_output=True,
        text=True,
        check=True
    )

    return result.stdout.strip()


def redis_int(key):
    value = redis_get(key)
    return int(value) if value else 0


def check(name, condition, details=""):
    global passed, total

    total += 1

    if condition:
        passed += 1

    print(
        f"{'PASS' if condition else 'FAIL'} | "
        f"{name}"
        + (f" | {details}" if details else "")
    )


def mutate(operation):
    return http_json(
        f"{AUTH_URL}/mutate",
        {
            "operation": operation,
            "user": USER,
            "relation": "viewer",
            "resource": RESOURCE
        }
    )


def resolve():
    return http_json(
        f"{PIP_URL}/resolve-relationship",
        {
            "user": USER,
            "relation": "can_read",
            "resource": RESOURCE
        }
    )


def evaluate():
    return http_json(
        f"{PDP_URL}/evaluate",
        {
            "user": USER,
            "resource": RESOURCE,
            "action": "edge:read"
        }
    )


def wait_for_processed(target):
    for _ in range(40):
        if redis_int("auth:sync:processed") >= target:
            return True

        time.sleep(0.25)

    return False


def publish_duplicate(event):
    """Publish the exact same event ID to test deduplication."""

    script = """
import json,sys
from confluent_kafka import Producer

event=json.load(sys.stdin)
producer=Producer({
    "bootstrap.servers":"kafka:19092",
    "acks":"all"
})
producer.produce(
    "edge2cloud.auth.relationships.v1",
    key=event["resource"].encode(),
    value=json.dumps(event).encode()
)
if producer.flush(10):
    raise RuntimeError("Duplicate publish timed out")
"""

    result = subprocess.run(
        [
            "docker", "compose", "exec", "-T",
            "auth-changes", "python", "-c", script
        ],
        input=json.dumps(event),
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr)


def run_tests():
    global relationship_granted

    print("=" * 76)
    print("EDGE2CLOUD KAFKA / OPENFGA INVALIDATION TESTS")
    print("=" * 76)

    epoch_key = f"auth:epoch:{RESOURCE}"

    # Test 1: Change API available
    status, health = http_json(
        f"{AUTH_URL}/health"
    )

    check(
        "Authorization change API healthy",
        status == 200
        and health.get("status") == "running"
    )

    # Test 2: Digital Twin is available.
    status, device = http_json(
        f"{DT_URL}/devices/actuator-001"
    )

    check(
        "Digital Twin observation exists",
        status == 200
        and device.get("device_id") == "actuator-001"
    )

    # Establish the initial state.
    before_epoch = redis_int(epoch_key)
    before_processed = redis_int(
        "auth:sync:processed"
    )

    # Test 3: Grant viewer relationship.
    status, grant = mutate("grant")

    relationship_granted = (
        status == 200
        and grant.get("status") == "applied"
    )

    check(
        "OpenFGA relationship granted",
        relationship_granted,
        str(grant)
    )

    if not relationship_granted:
        raise RuntimeError(
            "Cannot continue: grant unsuccessful"
        )

    # Test 4: Cloud relationship evidence is true.
    status, evidence = resolve()

    check(
        "PIP resolves granted relationship",
        status == 200
        and evidence.get("allowed") is True
    )

    # Test 5: Repeat and verify cached evidence.
    status, cached = resolve()

    check(
        "Relationship evidence cached",
        status == 200
        and cached.get("allowed") is True
        and cached.get("cache_hit") is True
    )

    # Test 6: PDP allows read.
    status, decision = evaluate()

    check(
        "PDP allows granted read",
        status == 200
        and decision.get("decision") == "ALLOW"
    )

    # Test 7: Revoke the relationship.
    status, revoke = mutate("revoke")

    check(
        "OpenFGA relationship revoked",
        status == 200
        and revoke.get("status") == "applied",
        str(revoke)
    )

    if status != 200:
        raise RuntimeError(
            "Revocation was not confirmed; inspect OpenFGA"
        )

    relationship_granted = False

    # Test 8: Current generation advances.
    after_epoch = redis_int(epoch_key)

    check(
        "Redis resource generation advanced",
        after_epoch >= before_epoch + 2,
        f"{before_epoch} -> {after_epoch}"
    )

    # Test 9: First check after revocation is false.
    status, evidence = resolve()

    check(
        "Stale relationship evidence not reused",
        status == 200
        and evidence.get("allowed") is False
    )

    # Test 10: PDP denies access.
    status, decision = evaluate()

    check(
        "PDP denies revoked read",
        status == 200
        and decision.get("decision") == "DENY"
        and decision.get("reason") == "RELATIONSHIP_FALSE"
    )

    # Test 11: Kafka consumer saw both events.
    observed = wait_for_processed(
        before_processed + 2
    )

    check(
        "Kafka consumer processed change events",
        observed
    )

    # Test 12: Replaying an event does not
    # increment the generation again.
    last_raw = redis_get(
        "auth:sync:last_event"
    )

    if last_raw:
        event = json.loads(last_raw)

        if (
            event.get("event_id")
            == revoke.get("kafka_event_id")
        ):
            stable_epoch = redis_int(epoch_key)
            stable_processed = redis_int(
                "auth:sync:processed"
            )

            publish_duplicate(event)

            time.sleep(2)

            check(
                "Duplicate event is idempotent",
                redis_int(epoch_key) == stable_epoch
                and redis_int(
                    "auth:sync:processed"
                ) == stable_processed
            )
        else:
            check(
                "Duplicate event is idempotent",
                False,
                "Latest consumed event was not revoke"
            )

    else:
        check(
            "Duplicate event is idempotent",
            False,
            "No consumed event available"
        )

    # Test 13: Digital Twin data preserved.
    status, device = http_json(
        f"{DT_URL}/devices/actuator-001"
    )

    check(
        "Digital Twin Redis state preserved",
        status == 200
        and device.get("device_id") == "actuator-001"
    )

    print("-" * 76)
    print(f"Results: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    try:
        success = run_tests()
        sys.exit(0 if success else 1)

    except Exception as exc:
        print(f"TEST ERROR: {exc}")
        sys.exit(1)

    finally:
        if relationship_granted:
            print(
                "Attempting cleanup of test relationship..."
            )

            try:
                status, result = mutate("revoke")

                print(
                    f"Cleanup status: {status}, "
                    f"result: {result}"
                )

            except Exception as exc:
                print(
                    f"Cleanup failed: {exc}"
                )
