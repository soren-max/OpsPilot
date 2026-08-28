import json
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

STATE_FILE = Path("/var/lib/opspilot-demo/demo-api.state")


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path == "/health":
            running = STATE_FILE.read_text().strip() == "running"
            self._json(200 if running else 503, {"status": "UP" if running else "DOWN"})
            return
        if parsed.path == "/tickets":
            query = parse_qs(parsed.query)
            service = query.get("service", ["demo-api"])[0]
            environment = query.get("environment", ["test"])[0]
            now = datetime.now(UTC)
            self._json(
                200,
                {
                    "tickets": [
                        {
                            "id": "SYN-101",
                            "title": "Synthetic service availability incident",
                            "status": "OPEN",
                            "service": service,
                            "environment": environment,
                            "summary": "The synthetic legacy service is unavailable.",
                            "resolution": None,
                            "created_at": (now - timedelta(minutes=1)).isoformat(),
                            "resolved_at": None,
                        }
                    ]
                },
            )
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/fault/stop":
            STATE_FILE.write_text("stopped\n")
            self._json(200, {"fault": "service-down"})
            return
        if self.path == "/fault/reset":
            STATE_FILE.write_text("running\n")
            self._json(200, {"status": "reset"})
            return
        self._json(404, {"error": "not_found"})

    def log_message(self, _format: str, *_args: object) -> None:
        return


ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
