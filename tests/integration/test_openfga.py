import json
import os
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_FILE = PROJECT_ROOT / ".env"

if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        key, separator, value = line.partition("=")

        if separator:
            os.environ.setdefault(
                key.strip(),
                value.strip().strip('"').strip("'")
            )


FGA_URL = os.getenv("FGA_URL", "http://localhost:8080")
STORE_ID = os.environ["FGA_STORE_ID"]
MODEL_ID = os.environ["FGA_MODEL_ID"]

tests = [
    ("operator-001", "can_read", True),
    ("operator-001", "can_start", True),
    ("operator-001", "can_maintain", False),

    ("technician-001", "can_read", True),
    ("technician-001", "can_start", False),
    ("technician-001", "can_maintain", True),

    ("viewer-001", "can_read", True),
    ("viewer-001", "can_start", False),
    ("viewer-001", "can_maintain", False)
]


def check_permission(user, relation):

    url = f"{FGA_URL}/stores/{STORE_ID}/check"

    payload = {
        "tuple_key": {
            "user": f"user:{user}",
            "relation": relation,
            "object": "device:actuator-001"
        },
        "authorization_model_id": MODEL_ID
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        result = json.loads(response.read().decode())

    return result["allowed"]


passed = 0

for user, relation, expected in tests:

    try:
        actual = check_permission(user, relation)

        success = actual == expected

        status = "PASS" if success else "FAIL"

        print(
            f"{status:5} | "
            f"{user:16} | "
            f"{relation:15} | "
            f"Expected: {expected!s:5} | "
            f"Actual: {actual}"
        )

        if success:
            passed += 1

    except Exception as error:
        print(f"ERROR | {user} | {relation} | {error}")


print()
print(f"Results: {passed}/{len(tests)} tests passed")

if passed != len(tests):
    raise SystemExit(1)
