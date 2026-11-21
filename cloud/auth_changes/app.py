
"""Development-only OpenFGA change producer.

Updates OpenFGA, advances the local Redis cache
generation, and publishes a Kafka event.

This endpoint is NOT a production administration API.
"""

import json
import os
import re
import threading
import uuid
import urllib.error
import urllib.request

from datetime import datetime, timezone
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer
)

import redis
from confluent_kafka import Producer


FGA_URL = os.getenv(
    "FGA_URL",
    "http://openfga:8080"
)

FGA_STORE_ID = os.environ["FGA_STORE_ID"]
FGA_MODEL_ID = os.environ["FGA_MODEL_ID"]

KAFKA_BOOTSTRAP = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "kafka:19092"
)

TOPIC = os.getenv(
    "KAFKA_AUTH_TOPIC",
    "edge2cloud.auth.relationships.v1"
)

cache = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=6379,
    decode_responses=True,
    socket_timeout=3
)

producer = Producer({
    "bootstrap.servers": KAFKA_BOOTSTRAP,
    "acks": "all",
    "enable.idempotence": True,
    "message.timeout.ms": 10000
})

# Serialize mutations in this demonstration API.
mutation_lock = threading.Lock()


def change_openfga(operation, user, relation, resource):
    tuple_key = {
        "user": user,
        "relation": relation,
        "object": resource
    }

    if operation == "grant":
        payload = {
            "writes": {
                "tuple_keys": [tuple_key],
                "on_duplicate": "ignore"
            },
            "authorization_model_id": FGA_MODEL_ID
        }

    else:
        payload = {
            "deletes": {
                "tuple_keys": [tuple_key],
                "on_missing": "ignore"
            },
            "authorization_model_id": FGA_MODEL_ID
        }

    request = urllib.request.Request(
        f"{FGA_URL}/stores/{FGA_STORE_ID}/write",
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
        response.read()


def publish_event(event):
    delivery = []

    def delivery_callback(error, message):
        delivery.append(error)

    producer.produce(
        TOPIC,
        key=event["resource"].encode("utf-8"),
        value=json.dumps(event).encode("utf-8"),
        callback=delivery_callback
    )

    remaining = producer.flush(10)

    if (
        remaining != 0
        or not delivery
        or delivery[0] is not None
    ):
        raise RuntimeError(
            "Kafka event delivery not confirmed"
        )


def validate_mutation(data):
    if (
        not isinstance(data, dict)
        or set(data) != {
            "operation",
            "user",
            "relation",
            "resource"
        }
    ):
        raise ValueError("Invalid mutation fields")

    operation = data["operation"]
    user = data["user"]
    relation = data["relation"]
    resource = data["resource"]

    if operation not in ("grant", "revoke"):
        raise ValueError("Unsupported operation")

    if (
        not isinstance(user, str)
        or not re.fullmatch(
            r"user:step9-[A-Za-z0-9_-]{1,48}",
            user
        )
    ):
        raise ValueError(
            "Only step9 test users are permitted"
        )

    if relation not in (
        "operator", "technician", "viewer"
    ):
        raise ValueError("Unsupported direct relation")

    if resource != "device:actuator-001":
        raise ValueError("Unsupported test resource")

    return operation, user, relation, resource


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
        if self.path != "/health":
            self.send_json(
                {"error": "Not found"},
                404
            )
            return

        try:
            cache.ping()

            self.send_json({
                "service": "auth-changes",
                "status": "running",
                "redis": "connected",
                "kafka_bootstrap": KAFKA_BOOTSTRAP
            })

        except redis.RedisError:
            self.send_json(
                {"status": "degraded"},
                503
            )

    def do_POST(self):
        if self.path != "/mutate":
            self.send_json(
                {"error": "Not found"},
                404
            )
            return

        try:
            length = int(
                self.headers.get(
                    "Content-Length", "0"
                )
            )

            if not 0 < length <= 4096:
                raise ValueError("Invalid request size")

            data = json.loads(
                self.rfile.read(length)
            )

            operation, user, relation, resource = (
                validate_mutation(data)
            )

        except (
            ValueError,
            TypeError,
            json.JSONDecodeError
        ) as exc:
            self.send_json(
                {"error": str(exc)},
                400
            )
            return

        with mutation_lock:
            # If Redis is already unavailable, do not
            # deliberately perform a new OpenFGA mutation.
            try:
                cache.ping()

            except redis.RedisError:
                self.send_json({
                    "error": "Redis unavailable; mutation not attempted"
                }, 503)
                return

            try:
                change_openfga(
                    operation,
                    user,
                    relation,
                    resource
                )

            except (
                urllib.error.URLError,
                TimeoutError,
                OSError
            ) as exc:
                self.send_json({
                    "error": "OpenFGA mutation failed",
                    "details": str(exc)
                }, 502)
                return

            # Advance the local generation before
            # returning a successful mutation response.
            try:
                generation = cache.incr(
                    f"auth:epoch:{resource}"
                )

            except redis.RedisError:
                self.send_json({
                    "error": "OpenFGA changed but local invalidation failed",
                    "mutation_may_have_succeeded": True
                }, 503)
                return

            event = {
                "schema_version": 1,
                "event_id": str(uuid.uuid4()),
                "event_type": "relationship.changed",
                "operation": operation,
                "user": user,
                "relation": relation,
                "resource": resource,
                "model_version": FGA_MODEL_ID,
                "timestamp": datetime.now(
                    timezone.utc
                ).isoformat()
            }

            try:
                publish_event(event)

            except Exception as exc:
                self.send_json({
                    "error": "OpenFGA changed and local cache invalidated, but Kafka publication failed",
                    "mutation_may_have_succeeded": True,
                    "local_generation": generation,
                    "details": str(exc)
                }, 503)
                return

        self.send_json({
            "status": "applied",
            "operation": operation,
            "user": user,
            "relation": relation,
            "resource": resource,
            "local_generation": generation,
            "kafka_event_id": event["event_id"],
            "kafka_published": True
        })


if __name__ == "__main__":
    print(
        "Authorization change API starting...",
        flush=True
    )

    ThreadingHTTPServer(
        ("0.0.0.0", 8000),
        Handler
    ).serve_forever()
