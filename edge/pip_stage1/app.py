
"""Edge2Cloud Local PIP Stage 1.

Authoritative relationship cache with:
- Redis TTL
- OpenFGA model version
- Resource-scoped generation keys
- Race-aware cache lookup and population

This service returns evidence, not final
authorization decisions.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.request

from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer
)

import redis


REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

CLOUD_PIP_URL = os.getenv(
    "CLOUD_PIP_URL",
    "http://cloud-service:8000"
)

CACHE_TTL = int(
    os.getenv("CACHE_TTL_SECONDS", "5")
)

FGA_MODEL_ID = os.environ["FGA_MODEL_ID"]

cache = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
    socket_timeout=3
)

MAX_REQUEST = 4096


def get_generation(resource):
    value = cache.get(
        f"auth:epoch:{resource}"
    )

    return int(value) if value is not None else 0


def relationship_key(user, relation, resource, generation):
    payload = json.dumps(
        {
            "user": user,
            "relation": relation,
            "resource": resource,
            "model_version": FGA_MODEL_ID,
            "generation": generation
        },
        sort_keys=True,
        separators=(",", ":")
    )

    digest = hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()

    return f"auth:rel:v9:{digest}"


def fetch_from_cloud(user, relation, resource):
    payload = {
        "user": user,
        "relation": relation,
        "resource": resource
    }

    request = urllib.request.Request(
        f"{CLOUD_PIP_URL}/check-relationship",
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
        or result.get("model_version") != FGA_MODEL_ID
    ):
        raise ValueError(
            "Cloud PIP returned invalid relationship evidence"
        )

    return result


def resolve_relationship(user, relation, resource):
    started = time.perf_counter()

    # Retry if a Kafka event or direct mutation
    # changes the resource generation mid-request.
    for attempt in range(3):
        generation = get_generation(resource)

        key = relationship_key(
            user, relation, resource, generation
        )

        cached = cache.get(key)

        if cached is not None:
            evidence = json.loads(cached)

            if (
                evidence.get("user") != user
                or evidence.get("relation") != relation
                or evidence.get("resource") != resource
                or evidence.get("model_version") != FGA_MODEL_ID
                or type(evidence.get("allowed")) is not bool
            ):
                raise ValueError("Invalid cached evidence")

            # Do not return evidence if invalidation
            # happened during the Redis read.
            if get_generation(resource) != generation:
                continue

            return {
                **evidence,
                "source": "openfga",
                "cache_hit": True,
                "cloud_fallback": False,
                "cache_ttl_seconds": cache.ttl(key),
                "cache_generation": generation,
                "pip_latency_ms": round(
                    (time.perf_counter() - started) * 1000,
                    3
                )
            }

        evidence = fetch_from_cloud(
            user, relation, resource
        )

        # If a mutation occurred during the cloud
        # lookup, discard this result and retry.
        if get_generation(resource) != generation:
            continue

        value = {
            "user": user,
            "relation": relation,
            "resource": resource,
            "allowed": evidence["allowed"],
            "source": "openfga",
            "model_version": FGA_MODEL_ID,
            "retrieved_at": time.time()
        }

        cache.setex(
            key,
            CACHE_TTL,
            json.dumps(value)
        )

        # Check once more after the cache write.
        # The old generation key becomes unreachable
        # after an invalidation event.
        if get_generation(resource) != generation:
            continue

        return {
            **value,
            "cache_hit": False,
            "cloud_fallback": True,
            "cache_ttl_seconds": CACHE_TTL,
            "cache_generation": generation,
            "pip_latency_ms": round(
                (time.perf_counter() - started) * 1000,
                3
            )
        }

    raise RuntimeError(
        "Relationship generation changed repeatedly"
    )


class Handler(BaseHTTPRequestHandler):

    def send_json(self, value, status=200):
        body = json.dumps(value).encode("utf-8")

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
        if self.path != "/health":
            self.send_json(
                {"error": "not found"},
                404
            )
            return

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
                503
            )

    def do_POST(self):
        if self.path != "/resolve-relationship":
            self.send_json(
                {"error": "not found"},
                404
            )
            return

        try:
            length = int(
                self.headers.get(
                    "Content-Length", "0"
                )
            )

            if not 0 < length <= MAX_REQUEST:
                raise ValueError("Invalid request size")

            payload = json.loads(
                self.rfile.read(length)
            )

            if (
                not isinstance(payload, dict)
                or set(payload) != {
                    "user", "relation", "resource"
                }
            ):
                raise ValueError("Invalid relationship request")

            user = payload["user"]
            relation = payload["relation"]
            resource = payload["resource"]

            if (
                not isinstance(user, str)
                or not user.startswith("user:")
                or len(user) > 128
                or not isinstance(relation, str)
                or relation not in (
                    "can_read",
                    "can_start",
                    "can_maintain"
                )
                or not isinstance(resource, str)
                or not resource.startswith("device:")
                or len(resource) > 128
            ):
                raise ValueError("Invalid relationship identifiers")

        except (
            ValueError,
            TypeError,
            json.JSONDecodeError
        ) as exc:
            self.send_json({
                "error": str(exc)
            }, 400)
            return

        try:
            result = resolve_relationship(
                user, relation, resource
            )

            self.send_json(result)

        except (
            redis.RedisError,
            urllib.error.URLError,
            TimeoutError,
            OSError,
            ValueError,
            RuntimeError
        ) as exc:
            print(
                f"PIP evidence error: {exc}",
                flush=True
            )

            self.send_json({
                "error": "Relationship evidence unavailable"
            }, 503)


if __name__ == "__main__":
    print(
        "Edge PIP Stage 1 starting...",
        flush=True
    )

    ThreadingHTTPServer(
        ("0.0.0.0", 8000),
        Handler
    ).serve_forever()
