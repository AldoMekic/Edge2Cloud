
import json
import os
import threading
import time

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

import paho.mqtt.client as mqtt
import redis


MQTT_HOST = os.getenv("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

MAX_AGE = float(os.getenv("DT_MAX_AGE_SECONDS", "10"))
STORAGE_TTL = int(os.getenv("DT_STORAGE_TTL_SECONDS", "120"))

cache = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
    socket_timeout=2
)

observation_lock = threading.Lock()
mqtt_connected = threading.Event()


def utc_now():
    return datetime.now(timezone.utc)


def parse_timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp must be a string")

    parsed = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    if parsed.tzinfo is None:
        raise ValueError("Timestamp requires timezone")

    return parsed.astimezone(timezone.utc)


def redis_key(device_id):
    return f"dt:device:{device_id}"


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        mqtt_connected.set()
        client.subscribe("dt/+/+/telemetry", qos=1)
        print("Digital Twin subscribed to telemetry", flush=True)
    else:
        mqtt_connected.clear()
        print(f"MQTT connection failed: {reason_code}", flush=True)


def on_disconnect(client, userdata, disconnect_flags,
                  reason_code, properties):
    mqtt_connected.clear()


def on_message(client, userdata, message):
    try:
        parts = message.topic.split("/")

        if len(parts) != 4 or parts[0] != "dt" or parts[3] != "telemetry":
            raise ValueError("Invalid telemetry topic")

        edge_id, device_id = parts[1], parts[2]

        payload = json.loads(message.payload.decode("utf-8"))

        if not isinstance(payload, dict):
            raise ValueError("Expected JSON object")

        if (
            payload.get("device_id") != device_id
            or payload.get("edge_id") != edge_id
        ):
            raise ValueError("Topic and payload identifiers differ")

        boot_id = payload.get("boot_id")
        sequence = payload.get("sequence")
        state = payload.get("state")
        temperature = payload.get("temperature")

        if not isinstance(boot_id, str) or not boot_id:
            raise ValueError("Invalid boot identifier")

        if type(sequence) is not int or sequence < 1:
            raise ValueError("Invalid sequence number")

        if state not in ("IDLE", "RUNNING", "STOPPED", "FAULT"):
            raise ValueError("Unsupported device state")

        if (
            type(temperature) not in (int, float)
            or not -100 <= temperature <= 500
        ):
            raise ValueError("Invalid temperature")

        source_time = parse_timestamp(payload["timestamp"])
        received_time = utc_now()

        if (source_time - received_time).total_seconds() > 5:
            raise ValueError("Telemetry timestamp is in the future")

        observation = {
            "device_id": device_id,
            "edge_id": edge_id,
            "boot_id": boot_id,
            "sequence": sequence,
            "state": state,
            "temperature": temperature,
            "safety_status": payload.get("safety_status"),
            "source_timestamp": source_time.isoformat(),
            "received_at": received_time.isoformat(),
            "source": f"mqtt:{message.topic}"
        }

        key = redis_key(device_id)

        with observation_lock:
            previous_raw = cache.get(key)

            if previous_raw:
                previous = json.loads(previous_raw)

                previous_time = parse_timestamp(
                    previous["source_timestamp"]
                )

                if source_time < previous_time:
                    print("Rejected older telemetry", flush=True)
                    return

                if (
                    previous.get("boot_id") == boot_id
                    and sequence <= previous.get("sequence", 0)
                ):
                    print("Rejected duplicate/out-of-order telemetry", flush=True)
                    return

            cache.setex(
                key,
                STORAGE_TTL,
                json.dumps(observation)
            )

        print(
            f"Digital Twin updated: {device_id}, "
            f"state={state}, temperature={temperature}",
            flush=True
        )

    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        print(f"Invalid telemetry: {exc}", flush=True)

    except redis.RedisError as exc:
        print(f"Redis failure: {exc}", flush=True)


def get_device(device_id):
    raw = cache.get(redis_key(device_id))

    if raw is None:
        return None

    observation = json.loads(raw)

    source_time = parse_timestamp(
        observation["source_timestamp"]
    )

    age = max(
        0.0,
        (utc_now() - source_time).total_seconds()
    )

    return {
        **observation,
        "age_seconds": round(age, 3),
        "freshness": (
            "FRESH" if age <= MAX_AGE else "STALE"
        )
    }


class Handler(BaseHTTPRequestHandler):

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            try:
                cache.ping()

                ready = mqtt_connected.is_set()

                self.send_json({
                    "service": "digital-twin",
                    "status": "running" if ready else "degraded",
                    "redis": "connected",
                    "mqtt": "connected" if ready else "disconnected"
                }, 200 if ready else 503)

            except redis.RedisError:
                self.send_json(
                    {"error": "Redis unavailable"},
                    503
                )
            return

        path = urlparse(self.path).path

        if path.startswith("/devices/"):
            device_id = unquote(path[len("/devices/"):])

            if (
                not device_id
                or "/" in device_id
                or len(device_id) > 128
            ):
                self.send_json({"error": "Invalid device ID"}, 400)
                return

            try:
                observation = get_device(device_id)

                if observation is None:
                    self.send_json({
                        "error": "Device observation unavailable",
                        "freshness": "UNKNOWN"
                    }, 404)
                else:
                    self.send_json(observation)

            except redis.RedisError:
                self.send_json(
                    {"error": "Redis unavailable"},
                    503
                )

            except (ValueError, KeyError, TypeError):
                self.send_json(
                    {"error": "Invalid stored observation"},
                    503
                )
            return

        self.send_json({"error": "Not found"}, 404)


def start_http():
    ThreadingHTTPServer(
        ("0.0.0.0", 8000),
        Handler
    ).serve_forever()


if __name__ == "__main__":
    threading.Thread(
        target=start_http,
        daemon=True
    ).start()

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="edge-digital-twin",
        protocol=mqtt.MQTTv5
    )

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            client.loop_forever()
        except OSError as exc:
            mqtt_connected.clear()
            print(f"MQTT unavailable: {exc}", flush=True)
            time.sleep(2)
