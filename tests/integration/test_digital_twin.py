
"""Digital Twin and PDP integration tests."""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

from datetime import datetime, timezone


DT_URL = "http://127.0.0.1:8005"
PDP_URL = "http://127.0.0.1:8004"

DEVICE_ID = "actuator-001"
TOPIC = f"dt/edge-001/{DEVICE_ID}/telemetry"

BOOT_ID = str(uuid.uuid4())

passed = 0
total = 0


def docker(*args):
    return subprocess.run(
        ["docker", "compose", *args],
        check=True,
        capture_output=True,
        text=True
    )


def get_json(url):
    try:
        with urllib.request.urlopen(
            url, timeout=5
        ) as response:
            return response.status, json.load(response)

    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def post_json(url, payload):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request, timeout=10
        ) as response:
            return response.status, json.load(response)

    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def publish_telemetry(sequence, state, temperature):
    payload = {
        "edge_id": "edge-001",
        "device_id": DEVICE_ID,
        "boot_id": BOOT_ID,
        "sequence": sequence,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "state": state,
        "temperature": temperature,
        "safety_status": (
            "SAFE" if state == "IDLE" and temperature < 70
            else "UNSAFE"
        )
    }

    docker(
        "exec", "-T", "mqtt",
        "mosquitto_pub",
        "-h", "127.0.0.1",
        "-p", "1883",
        "-t", TOPIC,
        "-q", "1",
        "-m", json.dumps(payload)
    )

    # Wait for asynchronous MQTT delivery.
    for _ in range(30):
        status, observation = get_json(
            f"{DT_URL}/devices/{DEVICE_ID}"
        )

        if (
            status == 200
            and observation.get("boot_id") == BOOT_ID
            and observation.get("sequence") == sequence
        ):
            return observation

        time.sleep(0.1)

    raise RuntimeError(
        "Digital Twin did not receive test telemetry"
    )


def evaluate_start():
    return post_json(
        f"{PDP_URL}/evaluate",
        {
            "user": "user:operator-001",
            "resource": f"device:{DEVICE_ID}",
            "action": "edge:start"
        }
    )


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


def run_tests():
    print("=" * 70)
    print("DIGITAL TWIN / MQTT / PDP INTEGRATION TESTS")
    print("=" * 70)

    # Test 1 and 2: Valid safe telemetry
    observation = publish_telemetry(
        1, "IDLE", 42.5
    )

    check(
        "Digital Twin telemetry received",
        (
            observation.get("state") == "IDLE"
            and observation.get("freshness") == "FRESH"
        )
    )

    status, result = evaluate_start()

    check(
        "Safe actuator may start",
        status == 200
        and result.get("decision") == "ALLOW"
        and result.get("policy_version") == "v2",
        result.get("reason", "")
    )

    # Test 3: Wrong operating state
    publish_telemetry(
        2, "RUNNING", 42.5
    )

    status, result = evaluate_start()

    check(
        "Running actuator denied",
        status == 200
        and result.get("decision") == "DENY"
        and result.get("reason") ==
            "DT_CONTEXT_CONSTRAINT_FALSE"
    )

    # Test 4: Unsafe temperature
    publish_telemetry(
        3, "IDLE", 85.0
    )

    status, result = evaluate_start()

    check(
        "Overheated actuator denied",
        status == 200
        and result.get("decision") == "DENY"
        and result.get("reason") ==
            "DT_CONTEXT_CONSTRAINT_FALSE"
    )

    # Test 5: Stale evidence
    publish_telemetry(
        4, "IDLE", 42.5
    )

    print("Waiting 11 seconds for telemetry to become stale...")
    time.sleep(11)

    status, result = evaluate_start()

    check(
        "Stale telemetry not authorized",
        status == 503
        and result.get("decision") == "INDETERMINATE"
        and result.get("reason") ==
            "DT_CONTEXT_UNAVAILABLE_OR_STALE"
    )

    print("-" * 70)
    print(f"Results: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    simulator_stopped = False

    try:
        print("Stopping simulator during controlled testing...")
        docker("stop", "iot-simulator")
        simulator_stopped = True

        # Let any in-flight telemetry finish.
        time.sleep(0.5)

        success = run_tests()
        sys.exit(0 if success else 1)

    except Exception as exc:
        print(f"TEST ERROR: {exc}")
        sys.exit(1)

    finally:
        if simulator_stopped:
            print("Restarting IoT simulator...")
            try:
                docker("start", "iot-simulator")
            except Exception as exc:
                print(f"Simulator restart failed: {exc}")
