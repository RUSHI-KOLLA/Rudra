"""Minimal web server for the VG browser interface.

Production-ready for public SaaS hosting:
- API keys are provided per-request via X-API-Key header (never stored on server)
- CORS enabled for cross-origin access
- No server-side key storage for multi-user safety

Phase 3 dispatch (design doc §22):

    POST /api/analyze          -> debate pipeline, gated on debate_enabled
    POST /api/incident-match   -> incident extraction/matching (zero agents)
    POST /api/incident-outcome -> record an outcome onto a card

Typed failure contract:

- 401  missing/invalid X-API-Key (existing shape, unchanged)
- 409  forecast mode disabled (flag off — checked BEFORE any coordinator)
- 422  needs_manual_entry (extraction incomplete; paste spooled)
- 503  IncidentStoreError (embedder/Chroma down; reason included)
- 404  unknown incident_id on /api/incident-outcome

Reading the POST body happens exactly once in ``do_POST``; handlers receive
the parsed dict, so ``mode=debate`` on an incident route cannot re-read an
already-consumed stream.
"""

from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from vg.config import config
from vg.incidents.investigation import investigate


STATIC_DIR = Path(__file__).resolve().parent / "static"


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2, default=str).encode("utf-8")


class VGWebHandler(BaseHTTPRequestHandler):
    """Serve the browser UI and analysis API."""

    server_version = "VGWeb/2.0"

    # ─── CORS ───────────────────────────────────────────────────────
    def _send_cors_headers(self) -> None:
        """Add CORS headers to every response."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")

    def do_OPTIONS(self) -> None:  # noqa: N802
        """Handle CORS preflight requests."""
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    # ─── GET ────────────────────────────────────────────────────────
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path in {"/", "/index.html"}:
            self._serve_file(STATIC_DIR / "index.html")
            return

        if parsed.path == "/api/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": "vg-web",
                    "version": "2.0",
                    "mode": "saas",
                    "modes": ["investigate"],
                },
            )
            return

        if parsed.path.startswith("/static/"):
            rel_path = parsed.path.removeprefix("/static/").strip("/")
            file_path = (STATIC_DIR / rel_path).resolve()
            if STATIC_DIR not in file_path.parents and file_path != STATIC_DIR:
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "Forbidden"})
                return
            self._serve_file(file_path)
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    # ─── POST ───────────────────────────────────────────────────────
    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path

        # Dispatch table over the routes. The investigator is the only
        # analysis endpoint — the debate and paste-a-case flows are gone.
        dispatch: dict[str, Callable[[dict[str, Any]], None]] = {
            "/api/incident-investigate": self._handle_incident_investigate,
        }

        handler = dispatch.get(route)
        if handler is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        # Body is read exactly once, here, and handed to the handler.
        try:
            body = self._read_json_body()
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        if not isinstance(body, dict):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "Request body must be a JSON object."},
            )
            return

        handler(body)

    # ─── Helpers ────────────────────────────────────────────────────
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        """Keep request logging concise. Never log API keys."""
        print(f"[vg-web] {self.address_string()} - {format % args}")

    def _read_json_body(self) -> dict[str, Any]:
        content_length = self.headers.get("Content-Length")
        if not content_length:
            raise ValueError("Missing request body.")

        try:
            body_size = int(content_length)
        except ValueError as exc:
            raise ValueError("Invalid Content-Length.") from exc

        raw_body = self.rfile.read(body_size)
        if not raw_body:
            raise ValueError("Empty request body.")

        try:
            return json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON.") from exc

    def _serve_file(self, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        content_type, _ = mimetypes.guess_type(str(file_path))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _groq_key(self) -> str:
        """Per-request key; falls back to a server-side key when configured."""
        submitted = self.headers.get("X-API-Key", "").strip()
        return submitted or (config.groq_api_key or os.getenv("GROQ_API_KEY") or "")

    def _require_key(self) -> bool:
        """401 with the existing shape when no key is available."""
        if self._groq_key():
            return True
        self._send_json(
            HTTPStatus.UNAUTHORIZED,
            {
                "error": "Groq API key required.",
                "hint": "Provide X-API-Key or configure GROQ_API_KEY on the server.",
            },
        )
        return False

    def _handle_incident_investigate(self, body: dict[str, Any]) -> None:
        """POST /api/incident-investigate — question-driven mini CID investigation.

        Returns structured findings with provenance tags (documented,
        reported_unconfirmed, inferred, speculative), contradictions, and synthesis.
        """
        if not self._require_key():
            return

        question = str(body.get("question", "") or "").strip()

        if not question:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Question is required."})
            return

        try:
            result = investigate(question)
        except Exception as exc:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "Investigation failed.", "detail": str(exc)},
            )
            return

        self._send_json(HTTPStatus.OK, result)

    # ─── Server ──────────────────────────────────────────────────────
def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Start the threaded VG web server."""
    print("  Mode: Mini CID Investigator")
    print("  Server: VGWeb/2.0")
    print("  Endpoint: POST /api/incident-investigate")

    server_key = os.getenv("GROQ_API_KEY")
    if server_key:
        print("  Server fallback key: ✓ configured (synthesis)")
    else:
        print("  Server fallback key: ✗ not set (mechanical synthesis only)")

    server = ThreadingHTTPServer((host, port), VGWebHandler)
    print(f"\nVG web interface running at http://{host}:{port}")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping VG web interface...")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
