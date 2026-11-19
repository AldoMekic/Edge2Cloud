
"""Edge2Cloud Local PDP.

Combines:
- ODRL policy evaluation
- OpenFGA relationship evidence via PIP Stage 1
- Digital Twin context

Completed decisions may generate asynchronous
AI prefetch observations. AI never changes a decision.
"""

import json
import os
import queue
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from datetime import datetime, timezone
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer
)
from pathlib import Path

from policy_engine import (
    PolicyError,
    select_requirement,
    applicable_rules,
    evaluate_context_requirements,
    parse_instant
)


PIP_URL = os.getenv(
    "LOCAL_PIP_URL",
    "http://pip-stage1:8000"
)

DT_URL = os.getenv(
    "DIGITAL_TWIN_URL",
    "http://digital-twin:8000"
)

AI_URL = os.getenv(
    "AI_PREFETCH_URL",
    "http://ai-prefetch:8000"
)

POLICY_DIR = Path(
    os.getenv("POLICY_DIR", "/app/policies")
)

DT_MAX_AGE = float(
    os.getenv("DT_MAX_AGE_SECONDS", "10")
)

MAX_SIZE = 65536

# A bounded queue prevents request handling from
# blocking on the AI service.
observation_queue = queue.Queue(maxsize=128)


def observation_worker():
    """Send completed PDP observations asynchronously."""

    while True:
        payload = observation_queue.get()

        try:
            request = urllib.request.Request(
                f"{AI_URL}/observe",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json"
                },
                method="POST"
            )

            with urllib.request.urlopen(
                request,
                timeout=8
            ) as response:
                result = json.load(response)

            print(
                f"AI observation: "
                f"{result.get('prefetch_status')}",
                flush=True
            )

        except Exception as exc:
            # An AI failure never changes a PDP decision.
            print(
                f"AI observation failed: {exc}",
                flush=True
            )

        finally:
            observation_queue.task_done()


def queue_observation(user, resource, action, result):
    if (
        result.get("decision") not in ("ALLOW", "DENY")
        or not result.get("relationship")
    ):
        return

    payload = {
        "user": user,
        "resource": resource,
        "action": action,
        "decision": result["decision"]
    }

    try:
        observation_queue.put_nowait(payload)
    except queue.Full:
        print(
            "AI observation queue full; event dropped",
            flush=True
        )


def read_policy(resource):
    index = json.loads(
        (POLICY_DIR / "index.json").read_text(
            encoding="utf-8"
        )
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

    return json.loads(
        (POLICY_DIR / filename).read_text(
            encoding="utf-8"
        )
    )


def fetch_relation(user, relation, resource):
    payload = {
        "user": user,
        "relation": relation,
        "resource": resource
    }

    request = urllib.request.Request(
        f"{PIP_URL}/resolve-relationship",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    with urllib.request.urlopen(
        request,
        timeout=7
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


def fetch_device_context(resource):
    if not resource.startswith("device:"):
        raise ValueError("Unsupported context resource")

    device_id = resource.split(":", 1)[1]

    url = (
        f"{DT_URL}/devices/"
        f"{urllib.parse.quote(device_id, safe='')}"
    )

    with urllib.request.urlopen(
        url,
        timeout=3
    ) as response:
        result = json.load(response)

    if (
        not isinstance(result, dict)
        or result.get("device_id") != device_id
        or not isinstance(result.get("source"), str)
        or not result["source"].startswith("mqtt:dt/")
        or type(result.get("sequence")) is not int
        or type(result.get("temperature")) not in (int, float)
        or result.get("state") not in (
            "IDLE", "RUNNING", "STOPPED", "FAULT"
        )
    ):
        raise ValueError("Invalid Digital Twin observation")

    source_time = parse_instant(
        result["source_timestamp"]
    )

    age = (
        datetime.now(timezone.utc) - source_time
    ).total_seconds()

    if (
        age < -5
        or age > DT_MAX_AGE
        or result.get("freshness") != "FRESH"
    ):
        raise ValueError("Digital Twin evidence is stale")

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

    try:
        evidence = fetch_relation(
            user,
            relation,
            resource
        )

    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
        KeyError,
        TypeError
    ):
        return {
            **base,
            "decision": "INDETERMINATE",
            "reason": "PIP_UNAVAILABLE_OR_INVALID"
        }

    evidence_fields = {
        "relationship": relation,
        "evidence_source": evidence["source"],
        "model_version": evidence["model_version"],
        "cache_hit": evidence["cache_hit"],
        "cloud_fallback": evidence["cloud_fallback"]
    }

    if not evidence["allowed"]:
        return {
            **base,
            **evidence_fields,
            "decision": "DENY",
            "reason": "RELATIONSHIP_FALSE"
        }

    permissions = applicable_rules(
        policy,
        "permission",
        resource,
        action,
        now
    )

    context_results = []
    context_details = None
    context_unknown = False

    for rule in permissions:
        requirements = rule.get(
            "edge:requiredContext",
            []
        )

        if not requirements:
            context_results.append(True)
            continue

        try:
            observation = fetch_device_context(
                resource
            )

            satisfied = evaluate_context_requirements(
                requirements,
                observation
            )

            context_results.append(satisfied)

            context_details = {
                "device_state": observation["state"],
                "device_temperature": observation[
                    "temperature"
                ],
                "dt_sequence": observation["sequence"],
                "dt_age_seconds": observation[
                    "age_seconds"
                ]
            }

        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            ValueError,
            KeyError,
            TypeError
        ):
            context_unknown = True

    if any(context_results):
        return {
            **base,
            **evidence_fields,
            **(context_details or {}),
            "decision": "ALLOW",
            "reason": "POLICY_RELATIONSHIP_CONTEXT_SATISFIED"
        }

    if context_unknown:
        return {
            **base,
            **evidence_fields,
            "decision": "INDETERMINATE",
            "reason": "DT_CONTEXT_UNAVAILABLE_OR_STALE"
        }

    return {
        **base,
        **evidence_fields,
        **(context_details or {}),
        "decision": "DENY",
        "reason": "DT_CONTEXT_CONSTRAINT_FALSE"
    }


class Handler(BaseHTTPRequestHandler):

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")

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
                {"error": "not found"},
                404
            )

    def do_POST(self):
        if self.path != "/evaluate":
            self.send_json(
                {"error": "not found"},
                404
            )
            return

        try:
            length = int(
                self.headers.get(
                    "Content-Length",
                    "0"
                )
            )

            if length <= 0 or length > MAX_SIZE:
                raise ValueError("Invalid request size")

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
                or not data["resource"].startswith("device:")
                or not data["action"].startswith("edge:")
            ):
                raise ValueError(
                    "Unsupported identifiers"
                )

        except (
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError
        ) as exc:
            self.send_json(
                {"error": str(exc)},
                400
            )
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

        # Do not await any AI computation.
        queue_observation(
            data["user"],
            data["resource"],
            data["action"],
            result
        )

        status = (
            200
            if result["decision"] != "INDETERMINATE"
            else 503
        )

        self.send_json(result, status)


if __name__ == "__main__":
    print("Local PDP starting...", flush=True)

    threading.Thread(
        target=observation_worker,
        name="ai-observation-worker",
        daemon=True
    ).start()

    ThreadingHTTPServer(
        ("0.0.0.0", 8000),
        Handler
    ).serve_forever()
