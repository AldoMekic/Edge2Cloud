from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request
import json


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path == "/health":

            response = {
                "service": "edge",
                "status": "running"
            }

            self.send_json(response)

        elif self.path == "/test-cloud":

            try:
                url = "http://cloud-service:8000/health"

                with urllib.request.urlopen(url, timeout=5) as result:
                    cloud_response = json.loads(result.read())

                self.send_json({
                    "edge": "running",
                    "cloud_connection": "successful",
                    "cloud_response": cloud_response
                })

            except Exception as e:

                self.send_json({
                    "cloud_connection": "failed",
                    "error": str(e)
                }, status=503)

        else:

            self.send_json({"error": "Not found"}, status=404)

    def send_json(self, data, status=200):

        body = json.dumps(data).encode()

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
