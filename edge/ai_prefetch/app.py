
"""Edge2Cloud AI-assisted PIP prefetch service.

Predictions select which relationship to look up.
Only the existing PIP/OpenFGA chain provides evidence.

This service NEVER issues ALLOW or DENY decisions.
"""

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

from datetime import datetime, timezone
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer
)

import joblib


MODEL_PATH = "/app/model.joblib"
REPORT_PATH = "/app/training_report.json"

LOCAL_PIP_URL = os.getenv(
    "LOCAL_PIP_URL",
    "http://pip-stage1:8000"
)

CONFIDENCE_THRESHOLD = float(
    os.getenv("PREFETCH_CONFIDENCE_THRESHOLD", "0.55")
)

ALLOWED_RESOURCE = "device:actuator-001"

RELATION_BY_ACTION = {
    "edge:read": "can_read",
    "edge:start": "can_start",
    "edge:maintain": "can_maintain"
}

USER_HINT_BY_ID = {
    "user:operator-001": 0,
    "user:technician-001": 1,
    "user:viewer-001": 2
}

MAX_REQUEST_BYTES = 4096

if not 0 <= CONFIDENCE_THRESHOLD <= 1:
    raise ValueError("Confidence threshold must be 0..1")

bundle = joblib.load(MODEL_PATH)
model = bundle["model"]
action_codes = bundle["action_codes"]
actions = bundle["actions"]

with open(REPORT_PATH, encoding="utf-8") as file:
    training_report = json.load(file)


metrics = {
    "observations": 0,
    "predictions": 0,
    "prefetch_attempts": 0,
    "prefetch_successes": 0,
    "prefetch_failures": 0,
    "prefetch_cache_hits": 0,
    "skipped": 0
}

metrics_lock = threading.Lock()


def increment(name):
    with metrics_lock:
        metrics[name] += 1


def predict_next_action(user, action, decision):
    hint = USER_HINT_BY_ID.get(user)

    if hint is None:
        raise ValueError("Unknown demonstration user")

    if action not in action_codes:
        raise ValueError("Unsupported action")

    hour = datetime.now(timezone.utc).hour

    features = [[
        hint,
        action_codes[action],
        1 if decision == "ALLOW" else 0,
        hour
    ]]

    probabilities = model.predict_proba(features)[0]

    candidates = [
        {
            "action": actions[int(class_code)],
            "probability": float(probability)
        }
        for class_code, probability in zip(
            model.classes_,
            probabilities
        )
    ]

    winner = max(
        candidates,
        key=lambda item: item["probability"]
    )

    return {
        "predicted_action": winner["action"],
        "predicted_relation": RELATION_BY_ACTION[
            winner["action"]
        ],
        "confidence": round(
            winner["probability"], 6
        ),
        "candidate_probabilities": candidates
    }


def prefetch_relationship(user, resource, relation):
    payload = {
        "user": user,
        "resource": resource,
        "relation": relation
    }

    request = urllib.request.Request(
        f"{LOCAL_PIP_URL}/resolve-relationship",
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
        evidence = json.load(response)

    # Validate the identity and source of evidence.
    # Never use the AI prediction as evidence itself.
    if (
        not isinstance(evidence, dict)
        or evidence.get("user") != user
        or evidence.get("resource") != resource
        or evidence.get("relation") != relation
        or evidence.get("source") != "openfga"
        or type(evidence.get("allowed")) is not bool
        or type(evidence.get("cache_hit")) is not bool
        or type(evidence.get("cloud_fallback")) is not bool
        or not isinstance(
            evidence.get("model_version"), str
        )
    ):
        raise ValueError("PIP returned invalid evidence")

    return evidence


def handle_observation(data):
    increment("observations")

    if (
        not isinstance(data, dict)
        or set(data) != {
            "user",
            "resource",
            "action",
            "decision"
        }
    ):
        raise ValueError("Invalid observation fields")

    user = data["user"]
    resource = data["resource"]
    action = data["action"]
    decision = data["decision"]

    if (
        not isinstance(user, str)
        or not re.fullmatch(
            r"user:[A-Za-z0-9_-]{1,64}", user
        )
    ):
        raise ValueError("Invalid user identifier")

    if resource != ALLOWED_RESOURCE:
        raise ValueError("Unsupported resource")

    if action not in RELATION_BY_ACTION:
        increment("skipped")

        return {
            "prefetch_status": "skipped_unknown_action"
        }

    if decision not in ("ALLOW", "DENY"):
        raise ValueError("Invalid PDP decision")

    # Only completed ALLOW requests trigger prefetching
    # in this initial experiment.
    if decision != "ALLOW":
        increment("skipped")

        return {
            "prefetch_status": "skipped_denied"
        }

    if user not in USER_HINT_BY_ID:
        increment("skipped")

        return {
            "prefetch_status": "skipped_unknown_user"
        }

    prediction = predict_next_action(
        user, action, decision
    )

    increment("predictions")

    result = {
        **prediction,
        "model_type": "HistGradientBoostingClassifier",
        "prefetch_status": None
    }

    if prediction["confidence"] < CONFIDENCE_THRESHOLD:
        increment("skipped")
        result["prefetch_status"] = "skipped_low_confidence"
        return result

    increment("prefetch_attempts")

    try:
        evidence = prefetch_relationship(
            user,
            resource,
            prediction["predicted_relation"]
        )

        increment("prefetch_successes")

        if evidence["cache_hit"]:
            increment("prefetch_cache_hits")

        result.update({
            "prefetch_status": "success",
            "prefetched_relation": evidence["relation"],
            "authoritative_allowed": evidence["allowed"],
            "evidence_source": evidence["source"],
            "model_version": evidence["model_version"],
            "cache_hit": evidence["cache_hit"],
            "cloud_fallback": evidence["cloud_fallback"]
        })

    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError
    ):
        increment("prefetch_failures")
        result["prefetch_status"] = "failed"
        result["error"] = "Authoritative lookup unavailable"

    return result


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
                "service": "ai-prefetch",
                "status": "running",
                "model_loaded": True,
                "algorithm": "HistGradientBoostingClassifier",
                "dataset": "synthetic",
                "threshold": CONFIDENCE_THRESHOLD
            })
            return

        if self.path == "/metrics":
            with metrics_lock:
                snapshot = dict(metrics)

            self.send_json({
                "service": "ai-prefetch",
                "metrics": snapshot,
                "training": {
                    "dataset": "synthetic",
                    "accuracy": training_report["accuracy"],
                    "balanced_accuracy": training_report[
                        "balanced_accuracy"
                    ],
                    "majority_baseline_accuracy": training_report[
                        "majority_baseline_accuracy"
                    ]
                }
            })
            return

        self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path != "/observe":
            self.send_json({"error": "Not found"}, 404)
            return

        try:
            length = int(
                self.headers.get("Content-Length", "0")
            )

            if not 0 < length <= MAX_REQUEST_BYTES:
                raise ValueError("Invalid request size")

            payload = json.loads(
                self.rfile.read(length)
            )

            result = handle_observation(payload)

            self.send_json(result)

        except (
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError
        ) as error:
            self.send_json({
                "error": str(error)
            }, 400)

        except Exception as error:
            print(
                f"Unexpected AI service error: {error}",
                flush=True
            )
            self.send_json({
                "error": "Internal service error"
            }, 500)


if __name__ == "__main__":
    print(
        "AI Prefetch service starting...",
        flush=True
    )

    print(
        f"Confidence threshold: {CONFIDENCE_THRESHOLD}",
        flush=True
    )

    print(
        f"Synthetic model accuracy: "
        f"{training_report['accuracy']:.4f}",
        flush=True
    )

    ThreadingHTTPServer(
        ("0.0.0.0", 8000),
        Handler
    ).serve_forever()
