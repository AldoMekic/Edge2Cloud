
"""Local PDP experimental API for Edge2Cloud."""

import json
import os
import time
import urllib.error
import urllib.request

from datetime import datetime, timezone
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer
)
from pathlib import Path

from policy_engine import (
    PolicyError,
    select_requirement
)


PIP_URL = os.getenv(
    "LOCAL_PIP_URL",
    "http://pip-stage1:8000"
)

POLICY_DIR = Path(
    os.getenv("POLICY_DIR", "/app/policies")
)

MAX_SIZE = 65536


def read_policy(resource):
    index_path = POLICY_DIR / "index.json"

    index = json.loads(
        index_path.read_text(encoding="utf-8")
    )

    if not isinstance(index, dict):
        raise PolicyError("Invalid policy index")

    filename = index.get(resource)

    if filename is None:
        return None

    if (
        not isinstance(filename, str)
        or filename != Path(filename).name
        or not filename.endswith(".jsonld")
    ):
        raise PolicyError("Invalid policy filename")

    policy_path = POLICY_DIR / filename

    return json.loads(
        policy_path.read_text(encoding="utf-8")
    )


def fetch_relation(user, relation, resource):
    payload = {
        "user": user,
        "relation": relation,
        "resource": resource
    }

    request = urllib.request.Request(
        f"{PIP_URL}/resolve-relationship",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    with urllib.request.urlopen(
        request, timeout=7
    ) as response:
        result = json.load(response)

    if (
        not isinstance(result, dict)
        or result.get("user") != user
        or result.get("relation") != relation
        or result.get("resource") != resource
        or result.get("source") != "openfga"
        or type(result.get("allowed")) is not bool
        or type(result.get("cache_hit")) is not bool
        or type(result.get("cloud_fallback")) is not bool
        or not isinstance(
            result.get("model_version"), str
        )
    ):
        raise ValueError("Invalid PIP evidence")

    return result


def evaluate(user, resource, action):
    try:
        policy = read_policy(resource)

        if policy is None:
            return {
                "decision": "DENY",
                "reason": "NO_POLICY",
                "policy_version": None
            }

        # Use trusted server time, not client time.
        now = datetime.now(timezone.utc)

        initial, reason, relation = select_requirement(
            policy, resource, action, now
        )

        base = {
            "policy_uid": policy["uid"],
            "policy_version": policy["edge:version"]
        }

        if initial is not None:
            return {
                **base,
                "decision": initial,
                "reason": reason
            }

        try:
            evidence = fetch_relation(
                user, relation, resource
            )

        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            ValueError
        ):
            return {
                **base,
                "decision": "INDETERMINATE",
                "reason": "PIP_UNAVAILABLE_OR_INVALID"
            }

        return {
            **base,
            "decision": (
                "ALLOW" if evidence["allowed"]
                else "DENY"
            ),
            "reason": (
                "RELATIONSHIP_TRUE"
                if evidence["allowed"]
                else "RELATIONSHIP_FALSE"
            ),
            "relationship": relation,
            "evidence_source": evidence["source"],
            "model_version": evidence["model_version"],
            "cache_hit": evidence["cache_hit"],
            "cloud_fallback": evidence["cloud_fallback"]
        }

    except (
        PolicyError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        json.JSONDecodeError
    ):
        return {
            "decision": "INDETERMINATE",
            "reason": "POLICY_INVALID_OR_UNAVAILABLE"
        }


class Handler(BaseHTTPRequestHandler):

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()

        self.send_response(status)
        self.send_header(
            "Content-Type", "application/json"
        )
        self.send_header(
            "Content-Length", str(len(body))
        )
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.send_json({
                "service": "edge-pdp",
                "status": "running"
            })
        else:
            self.send_json(
                {"error": "not found"}, 404
            )

    def do_POST(self):
        if self.path != "/evaluate":
            self.send_json(
                {"error": "not found"}, 404
            )
            return

        try:
            length = int(
                self.headers.get(
                    "Content-Length", "0"
                )
            )

            if length <= 0 or length > MAX_SIZE:
                raise ValueError(
                    "Invalid request size"
                )

            data = json.loads(
                self.rfile.read(length)
            )

            if (
                not isinstance(data, dict)
                or set(data) != {
                    "user", "resource", "action"
                }
            ):
                raise ValueError(
                    "Expected user, resource, action only"
                )

            for name in (
                "user", "resource", "action"
            ):
                value = data[name]

                if (
                    not isinstance(value, str)
                    or not 0 < len(value) <= 256
                ):
                    raise ValueError(
                        f"Invalid {name}"
                    )

            if (
                not data["user"].startswith("user:")
                or not data["resource"].startswith(
                    "device:"
                )
                or not data["action"].startswith(
                    "edge:"
                )
            ):
                raise ValueError(
                    "Unsupported identifiers"
                )

        except (
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError
        ) as exc:
            self.send_json({
                "error": str(exc)
            }, 400)
            return

        start = time.perf_counter()

        result = evaluate(
            data["user"],
            data["resource"],
            data["action"]
        )

        result["pdp_latency_ms"] = round(
            (time.perf_counter() - start) * 1000,
            3
        )

        status = (
            200
            if result["decision"] != "INDETERMINATE"
            else 503
        )

        self.send_json(result, status)


if __name__ == "__main__":
    print(
        "Local PDP starting...",
        flush=True
    )

    ThreadingHTTPServer(
        ("0.0.0.0", 8000),
        Handler
    ).serve_forever()
