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

import asyncio
import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from vg.main import analyze_async
from vg.config import config
from vg.incidents.match import (
    ExtractionIncomplete,
    MAX_PASTE_CHARS,
    record_outcome,
    run_match,
)
from vg.incidents.store import IncidentStoreError


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
                    # R5: new FIELD on the existing route (no new endpoint).
                    # The panel uses it to decide whether to render Debate.
                    "debate_enabled": bool(config.debate_enabled),
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

        # Dispatch table over the three routes (design doc §22).
        dispatch: dict[str, Callable[[dict[str, Any]], None]] = {
            "/api/analyze": self._handle_analyze,
            "/api/incident-match": self._handle_incident_match,
            "/api/incident-outcome": self._handle_incident_outcome,
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

    def _send_match_error(self, exc: Exception) -> None:
        """Map incident-mode exceptions to the typed failure contract."""
        if isinstance(exc, ExtractionIncomplete):
            self._send_json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {
                    "error": "needs_manual_entry",
                    "status": "needs_manual_entry",
                    "missing": exc.missing,
                    "raw_paste": exc.raw_paste,
                    "spooled_path": exc.spooled_path,
                },
            )
            return
        if isinstance(exc, IncidentStoreError):
            self._send_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "service unavailable", "reason": str(exc)},
            )
            return
        if isinstance(exc, LookupError):
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"error": "unknown incident_id", "incident_id": str(exc.args[0])},
            )
            return
        self._send_json(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            {"error": "Match failed.", "detail": str(exc)},
        )

    # ─── Incident match endpoint ────────────────────────────────────
    def _handle_incident_match(self, body: dict[str, Any]) -> None:
        """POST /api/incident-match — extract card, score corpus, return matches.

        Two-phase: no ``extracted`` key -> ``status: reviewing`` (or 422
        needs_manual_entry); with ``extracted`` -> ``status: complete``.
        ``mode=debate`` reuses the same body (already read) and routes to
        the analyze handler.
        """
        mode = str(body.get("mode", "incident") or "incident").strip()
        if mode not in ("incident", "debate"):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "Invalid mode. Use 'incident' or 'debate'."},
            )
            return

        if mode == "debate":
            # Same parsed body — no second read of rfile (it is spent).
            self._handle_analyze(body)
            return

        if not self._require_key():
            return

        paste = str(body.get("paste", "") or "")
        if not paste.strip():
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Paste is required."})
            return

        extracted = body.get("extracted")
        if extracted is not None and not isinstance(extracted, dict):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "'extracted' must be an object when present."},
            )
            return

        try:
            result = asyncio.run(
                run_match(
                    paste=paste,
                    api_key=self._groq_key(),
                    extracted=extracted,
                )
            )
        except Exception as exc:
            self._send_match_error(exc)
            return

        if len(paste) > MAX_PASTE_CHARS:
            result.setdefault("truncated", True)
        self._send_json(HTTPStatus.OK, result)

    # ─── Incident outcome endpoint ──────────────────────────────────
    def _handle_incident_outcome(self, body: dict[str, Any]) -> None:
        """POST /api/incident-outcome — record outcome for a card."""
        if not self._require_key():
            return

        incident_id = str(body.get("incident_id", "") or "").strip()
        outcome_text = str(body.get("outcome_text", "") or "").strip()

        if not incident_id or not outcome_text:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "Both incident_id and outcome_text are required."},
            )
            return

        try:
            result = asyncio.run(
                record_outcome(
                    incident_id=incident_id,
                    outcome_text=outcome_text,
                    api_key=self._groq_key(),
                )
            )
        except Exception as exc:
            self._send_match_error(exc)
            return

        self._send_json(HTTPStatus.OK, result)

    # ─── Debate endpoint ────────────────────────────────────────────
    def _handle_analyze(self, body: dict[str, Any]) -> None:
        """POST /api/analyze — debate pipeline, gated on debate_enabled.

        Flag off -> 409 *before* any coordinator construction (a misrouted
        paste must not burn Tavily quota). Flag on -> unchanged behavior.
        """
        if not config.debate_enabled:
            self._send_json(
                HTTPStatus.CONFLICT,
                {"error": "forecast mode disabled"},
            )
            return

        if not self._require_key():
            return

        groq_key = self._groq_key()
        question = str(body.get("question", "") or "").strip()

        if not question:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Question is required."})
            return

        try:
            result = asyncio.run(
                analyze_async(
                    question,
                    use_enhanced=True,
                    api_key=groq_key,
                    provider="groq",
                )
            )
        except Exception as exc:
            error_msg = str(exc)
            if (
                "auth" in error_msg.lower()
                or "unauthorized" in error_msg.lower()
                or "invalid" in error_msg.lower()
            ):
                self._send_json(
                    HTTPStatus.UNAUTHORIZED,
                    {"error": "Invalid API key. Please check your Groq API key."},
                )
            else:
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "Analysis failed.", "detail": error_msg},
                )
            return

        self._send_json(
            HTTPStatus.OK,
            {
                "question": question,
                "enhanced": True,
                "result": result,
            },
        )


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Start the threaded VG web server."""
    print("  Mode: Public SaaS (per-request API keys)")
    print("  Server: VGWeb/2.0")
    print(
        f"  Debate mode: {'enabled' if config.debate_enabled else 'disabled (forecast disabled)'}"
    )

    server_key = config.groq_api_key or os.getenv("GROQ_API_KEY")
    if server_key:
        print("  Server fallback key: ✓ configured (for CLI)")
    else:
        print("  Server fallback key: ✗ not set (web users must provide their own)")

    tavily_key = config.tavily_api_key
    if tavily_key and "your" not in tavily_key.lower():
        print("  Tavily key: ✓ configured")
    else:
        print("  Tavily key: ✗ not set (web search disabled)")

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
