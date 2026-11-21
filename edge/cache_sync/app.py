
"""Kafka consumer for Edge2Cloud relationship invalidation."""

import json
import os
import re
import time

from datetime import datetime, timezone

import redis
from confluent_kafka import Consumer, KafkaException


KAFKA_BOOTSTRAP = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "kafka:19092"
)

TOPIC = os.getenv(
    "KAFKA_AUTH_TOPIC",
    "edge2cloud.auth.relationships.v1"
)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")

cache = redis.Redis(
    host=REDIS_HOST,
    port=6379,
    decode_responses=True,
    socket_timeout=3
)

# Atomically deduplicate an event and advance the
# resource generation. This does not delete
# Digital Twin observations or unrelated Redis keys.
INVALIDATE_LUA = """
local event_key = KEYS[1]
local epoch_key = KEYS[2]

local inserted = redis.call(
    'SET', event_key, '1', 'NX', 'EX', 86400
)

if not inserted then
    return -1
end

return redis.call('INCR', epoch_key)
"""


def validate_event(event):
    if not isinstance(event, dict):
        raise ValueError("Invalid event object")

    required = {
        "schema_version",
        "event_id",
        "event_type",
        "operation",
        "user",
        "relation",
        "resource",
        "timestamp",
        "model_version"
    }

    if not required.issubset(event):
        raise ValueError("Missing event fields")

    if event["schema_version"] != 1:
        raise ValueError("Unsupported event schema")

    if event["event_type"] != "relationship.changed":
        raise ValueError("Unsupported event type")

    if event["operation"] not in ("grant", "revoke"):
        raise ValueError("Invalid operation")

    if not re.fullmatch(
        r"[a-f0-9-]{36}",
        str(event["event_id"])
    ):
        raise ValueError("Invalid event identifier")

    if not re.fullmatch(
        r"device:[A-Za-z0-9_-]{1,64}",
        str(event["resource"])
    ):
        raise ValueError("Invalid resource")

    if not re.fullmatch(
        r"user:[A-Za-z0-9_-]{1,64}",
        str(event["user"])
    ):
        raise ValueError("Invalid user")

    if event["relation"] not in (
        "operator", "technician", "viewer"
    ):
        raise ValueError("Invalid relationship")

    if not isinstance(event["model_version"], str):
        raise ValueError("Invalid model version")

    if not isinstance(event["timestamp"], str):
        raise ValueError("Invalid timestamp")

    return event


def process_event(event):
    event = validate_event(event)

    event_id = event["event_id"]
    resource = event["resource"]

    generation = cache.eval(
        INVALIDATE_LUA,
        2,
        f"auth:event:{event_id}",
        f"auth:epoch:{resource}"
    )

    if generation == -1:
        print(
            f"DUPLICATE event={event_id}",
            flush=True
        )
        return

    cache.incr("auth:sync:processed")
    cache.set(
        "auth:sync:last_event",
        json.dumps(event)
    )

    print(
        f"INVALIDATED resource={resource} "
        f"generation={generation} "
        f"operation={event['operation']} "
        f"event={event_id}",
        flush=True
    )


def main():
    consumer = Consumer({
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "group.id": "edge2cloud-cache-sync-v1",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "allow.auto.create.topics": True,
        "session.timeout.ms": 10000
    })

    consumer.subscribe([TOPIC])

    print(
        f"Cache synchronization listening on {TOPIC}",
        flush=True
    )

    try:
        while True:
            try:
                message = consumer.poll(1.0)

                if message is None:
                    continue

                if message.error():
                    raise KafkaException(
                        message.error()
                    )

                try:
                    event = json.loads(
                        message.value().decode("utf-8")
                    )
                    process_event(event)

                except (
                    ValueError,
                    KeyError,
                    TypeError,
                    json.JSONDecodeError
                ) as exc:
                    # An invalid event must not silently
                    # advance the consumer offset.
                    print(
                        f"INVALID EVENT: {exc}",
                        flush=True
                    )
                    time.sleep(2)
                    continue

                consumer.commit(
                    message=message,
                    asynchronous=False
                )

            except (
                redis.RedisError,
                KafkaException,
                OSError
            ) as exc:
                print(
                    f"Synchronization error: {exc}",
                    flush=True
                )
                time.sleep(2)

    finally:
        consumer.close()


if __name__ == "__main__":
    main()
