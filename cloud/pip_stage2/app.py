import json
import os
import urllib.request
import urllib.error

from http.server import BaseHTTPRequestHandler, HTTPServer


FGA_URL = os.environ["FGA_URL"]
STORE_ID = os.environ["FGA_STORE_ID"]
MODEL_ID = os.environ["FGA_MODEL_ID"]


def check_relationship(user, relation, resource):
    """
    Retrieve relationship-based permission information
    from the authoritative OpenFGA service.

    This function does not make the final ODRL/PDP
    authorization decision.
    """

    url = f"{FGA_URL}/stores/{STORE_ID}/check"

    payload = {
        "tuple_key": {
            "user": user,
            "relation": relation,
            "object": resource
        },
        "authorization_model_id": MODEL_ID
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(
        request,
        timeout=5
    ) as response:

        result = json.loads(response.read())

    return result["allowed"]


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path == "/health":

            self.send_json({
                "service": "cloud-pip-stage2",
                "status": "running"
            })

        else:

            self.send_json(
                {"error": "Not found"},
                status=404
            )

    def do_POST(self):

        if self.path != "/check-relationship":

            self.send_json(
                {"error": "Not found"},
                status=404
            )
            return

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

            for field in ("user", "relation", "resource"):
                if not isinstance(data.get(field), str) or not data[field]:
                    self.send_json(
                        {"error": f"Invalid or missing {field}"},
                        status=400
                    )
                    return

            allowed = check_relationship(
                user=data["user"],
                relation=data["relation"],
                resource=data["resource"]
            )

            self.send_json({
                "source": "openfga",
                "user": data["user"],
                "relation": data["relation"],
                "resource": data["resource"],
                "allowed": allowed,
                "model_version": MODEL_ID
            })

        except (ValueError, json.JSONDecodeError):

            self.send_json(
                {"error": "Invalid JSON request"},
                status=400
            )

        except urllib.error.HTTPError as error:

            self.send_json({
                "error": "OpenFGA rejected the request",
                "upstream_status": error.code
            }, status=502)

        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError
        ):

            self.send_json({
                "error": "OpenFGA unavailable"
            }, status=503)

        except Exception:

            self.send_json({
                "error": "Internal service error"
            }, status=500)

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
        "Cloud PIP Stage 2 starting...",
        flush=True
    )

    HTTPServer(
        ("0.0.0.0", 8000),
        Handler
    ).serve_forever() 
