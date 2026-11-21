
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import redis


# --------------------------------------------------
# Configuration
# --------------------------------------------------

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

CLOUD_PIP_URL = os.getenv(
    "CLOUD_PIP_URL",
    "http://cloud-service:8000"
)

MODEL_ID = os.environ["FGA_MODEL_ID"]

CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "5"))

if CACHE_TTL <= 0:
    raise ValueError("CACHE_TTL_SECONDS must be positive")

# Redis client
cache = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2
)


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def make_cache_key(user, relation, resource):
    """
    Generate a stable cache key for one ReBAC
    predicate and authorization model version.
    """

    data = json.dumps(
        {
            "user": user,
            "relation": relation,
            "resource": resource,
            "model_version": MODEL_ID
        },
        sort_keys=True
    )

    digest = hashlib.sha256(data.encode()).hexdigest()

    return f"rebac:evidence:{digest}"


def fetch_cloud_relationship(user, relation, resource):
    """
    Fetch authoritative ReBAC information from
    Cloud PIP Stage 2.
    """

    payload = {
        "user": user,
        "relation": relation,
        "resource": resource
    }

    request = urllib.request.Request(
        url=f"{CLOUD_PIP_URL}/check-relationship",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(
        request,
        timeout=5
    ) as response:

        result = json.loads(
            response.read().decode("utf-8")
        )

    # Verify the authoritative response before caching.
    if (
        result.get("source") != "openfga"
        or result.get("user") != user
        or result.get("relation") != relation
        or result.get("resource") != resource
        or result.get("model_version") != MODEL_ID
        or type(result.get("allowed")) is not bool
    ):
        raise ValueError(
            "Invalid authoritative relationship response"
        )

    return result


# --------------------------------------------------
# PIP Stage 1
# --------------------------------------------------

def resolve_relationship(user, relation, resource):
    """
    Local-first relationship evidence resolution.

    1. Check Redis.
    2. Return valid cached evidence.
    3. On a miss, contact Cloud PIP Stage 2.
    4. Cache the authoritative response with TTL.

    This does NOT make a final authorization decision.
    """

    key = make_cache_key(user, relation, resource)

    # Stage 1: Local lookup
    cached = cache.get(key)

    if cached is not None:
        evidence = json.loads(cached)

        if (
            evidence.get("model_version") == MODEL_ID
            and type(evidence.get("allowed")) is bool
        ):
            remaining_ttl = cache.ttl(key)

            if remaining_ttl > 0:
                return {
                    **evidence,
                    "cache_hit": True,
                    "cloud_fallback": False,
                    "cache_ttl_remaining": remaining_ttl
                }

        # Reject inconsistent or expired cache entries.
        cache.delete(key)

    # Stage 2: Authoritative cloud fallback
    cloud_result = fetch_cloud_relationship(
        user, relation, resource
    )

    evidence = {
        "source": "openfga",
        "user": user,
        "relation": relation,
        "resource": resource,
        "allowed": cloud_result["allowed"],
        "model_version": MODEL_ID,
        "retrieved_at": current_timestamp()
    }

    # Bounded local reuse of verified evidence
    cache.setex(
        key,
        CACHE_TTL,
        json.dumps(evidence)
    )

    return {
        **evidence,
        "cache_hit": False,
        "cloud_fallback": True,
        "cache_ttl_remaining": CACHE_TTL
    }


# --------------------------------------------------
# HTTP API
# --------------------------------------------------

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path == "/health":
            try:
                cache.ping()

                self.send_json({
                    "service": "edge-pip-stage1",
                    "status": "running",
                    "redis": "connected"
                })

            except redis.RedisError:
                self.send_json(
                    {"error": "Redis unavailable"},
                    status=503
                )

        else:
            self.send_json(
                {"error": "Not found"},
                status=404
            )

    def do_POST(self):

        if self.path != "/resolve-relationship":
            self.send_json(
                {"error": "Not found"},
                status=404
            )
            return

        start = time.perf_counter()

        try:
            length = int(
                self.headers.get("Content-Length", "0")
            )

            if length <= 0 or length > 65536:
                self.send_json(
                    {"error": "Invalid request size"},
                    status=400
                )
                return

            body = self.rfile.read(length)
            data = json.loads(body)

            if not isinstance(data, dict):
                raise ValueError("Expected JSON object")

            for field in ("user", "relation", "resource"):
                value = data.get(field)

                if not isinstance(value, str) or not value:
                    raise ValueError(
                        f"Invalid or missing field: {field}"
                    )

            result = resolve_relationship(
                user=data["user"],
                relation=data["relation"],
                resource=data["resource"]
            )

            result["pip_latency_ms"] = round(
                (time.perf_counter() - start) * 1000,
                3
            )

            self.send_json(result)

        except (
            ValueError,
            json.JSONDecodeError
        ) as error:
            self.send_json(
                {"error": str(error)},
                status=400
            )

        except redis.RedisError:
            self.send_json(
                {"error": "Local Redis cache unavailable"},
                status=503
            )

        except (
            urllib.error.URLError,
            TimeoutError
        ):
            self.send_json(
                {
                    "error": "Authoritative cloud unavailable",
                    "status": "INDETERMINATE"
                },
                status=503
            )

        except Exception:
            self.send_json(
                {"error": "Internal service error"},
                status=500
            )

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json"
        )
        self.send_header(
            "Content-Length",
            str(len(body))
        )
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":

    print(
        "PIP Stage 1 starting...",
        flush=True
    )

    ThreadingHTTPServer(
        ("0.0.0.0", 8000),
        Handler
    ).serve_forever()
