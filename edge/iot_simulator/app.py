
import json
import os
import time
import uuid

from datetime import datetime, timezone

import paho.mqtt.client as mqtt


MQTT_HOST = os.getenv("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

EDGE_ID = os.getenv("EDGE_ID", "edge-001")
DEVICE_ID = os.getenv("DEVICE_ID", "actuator-001")

INTERVAL = float(os.getenv("TELEMETRY_INTERVAL", "2"))
TEMPERATURE = float(os.getenv("DEVICE_TEMPERATURE", "42.5"))
DEVICE_STATE = os.getenv("DEVICE_STATE", "IDLE")

BOOT_ID = str(uuid.uuid4())

TOPIC = f"dt/{EDGE_ID}/{DEVICE_ID}/telemetry"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"MQTT connection: {reason_code}", flush=True)


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id=f"simulator-{DEVICE_ID}",
    protocol=mqtt.MQTTv5
)

client.on_connect = on_connect

client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_start()

sequence = 0

try:
    while True:
        if not client.is_connected():
            time.sleep(1)
            continue

        sequence += 1

        payload = {
            "edge_id": EDGE_ID,
            "device_id": DEVICE_ID,
            "boot_id": BOOT_ID,
            "sequence": sequence,
            "timestamp": utc_now(),
            "state": DEVICE_STATE,
            "temperature": TEMPERATURE,
            "safety_status": (
                "SAFE" if TEMPERATURE < 70
                else "UNSAFE"
            )
        }

        message = json.dumps(payload)

        info = client.publish(
            TOPIC,
            message,
            qos=1,
            retain=False
        )

        info.wait_for_publish(timeout=5)

        print(
            f"Published {TOPIC}: {message}",
            flush=True
        )

        time.sleep(INTERVAL)

except KeyboardInterrupt:
    pass

finally:
    client.loop_stop()
    client.disconnect()
