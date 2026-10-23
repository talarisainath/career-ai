"""Development tool: receive parity fixtures POSTed from the browser.

The JavaScript engine is the reference implementation. Open the frontend in a
real browser, evaluate the fixture script (see tests/fixtures/README.md), and
this server writes the exact JSON output to tests/fixtures/parity_cases.json.

    python backend/tools/capture_fixtures.py
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "parity_cases.json"


class Handler(BaseHTTPRequestHandler):
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        if self.path != "/fixtures":
            self.send_response(404)
            self._cors()
            self.end_headers()
            return

        payload = json.loads(body.decode("utf-8"))
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        response = json.dumps({"saved": True, "cases": len(payload.get("cases", []))}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self._cors()
        self.end_headers()
        self.wfile.write(response)
        print(f"Saved {len(payload.get('cases', []))} cases to {TARGET}", flush=True)

    def log_message(self, *args) -> None:  # keep the console quiet
        pass


if __name__ == "__main__":
    print("Fixture collector listening on http://127.0.0.1:8770/fixtures", flush=True)
    HTTPServer(("127.0.0.1", 8770), Handler).serve_forever()
