"""Minimal web server for the VG browser interface.

One endpoint, one job:

    POST /api/incident-investigate -> the Mini CID investigation pipeline
    GET  /api/health                -> liveness + available modes

Access model
------------

The endpoint is **open by default**: every source it uses is keyless, so an
anonymous caller gets a full investigation with the deterministic mechanical
synthesis. Two keys exist and they are deliberately separate:

``X-API-Key``
    The *caller's own* Groq key (BYOK). It is used for the single synthesis
    call and is never stored. It is not authentication.

``X-VG-Access-Key``
    An optional *deployment* secret (``VG_ACCESS_KEY``). When configured,
    every request must present it or gets 401, and only then may the
    server's own ``GROQ_API_KEY`` be spent on synthesis. Without it, the
    server's Groq quota is never used on a caller's behalf.

Request budgets
---------------

- body <= ``VG_MAX_BODY_BYTES`` (64 KiB default), else 413
- question <= ``VG_MAX_QUESTION_CHARS`` (500 default), else 400
- ``VG_RATE_LIMIT_PER_MINUTE`` investigations per client address (10
  default), else 429
- cross-origin calls are refused unless the origin is in
  ``VG_ALLOWED_ORIGINS``

Failure contract:

- 401  missing/invalid deployment access key (only when one is configured)
- 400  missing question, malformed body, or over-long question
- 413  request body over the limit
- 429  rate limit exceeded
- 500  investigation failure (detail included)
- 404  unknown route

Reading the POST body happens exactly once in ``do_POST``; handlers receive
the parsed dict.
"""

from __future__ import annotations

import hmac
import json
import mimetypes
import os
import secrets
import threading
import time
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


class _PayloadTooLarge(ValueError):
    """Raised when a request body exceeds the configured limit."""


class _RateLimiter:
    """Fixed one-minute window limiter keyed by client address.

    One entry per client keeps a burst of calls from a single host, which is
    what protects the free upstream sources from being hammered by one
    abusive caller.
    """

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int) -> bool:
        """True when the call is within the budget. ``limit <= 0`` disables it."""
        if limit <= 0:
            return True
        now = time.monotonic()
        cutoff = now - 60.0
        with self._lock:
            hits = [stamp for stamp in self._hits.get(key, []) if stamp > cutoff]
            if len(hits) >= limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            # Drop clients that have gone quiet so the map cannot grow forever.
            if len(self._hits) > 512:
                self._hits = {
                    client: stamps
                    for client, stamps in self._hits.items()
                    if stamps and stamps[-1] > cutoff
                }
            return True

    def reset(self) -> None:
        """Forget every recorded call (used by the test suite)."""
        with self._lock:
            self._hits.clear()


#: One limiter for the process; the limit itself comes from the config.
_rate_limiter = _RateLimiter()


class VGWebHandler(BaseHTTPRequestHandler):
    """Serve the browser UI and analysis API."""

    server_version = "VGWeb/2.0"

    #: Socket timeout, so a stalled client cannot hold a worker forever.
    timeout = 30

    # ─── CORS ───────────────────────────────────────────────────────
    def _send_cors_headers(self) -> None:
        """Allow cross-origin calls only from explicitly allowed origins.

        The bundled UI is same-origin, so the default is to send no CORS
        headers at all — a wildcard would let any site drive the endpoint
        and burn the operator's quota.
        """
        origin = self.headers.get("Origin")
        allowed = config.allowed_origins or ()
        if not origin or (origin not in allowed and "*" not in allowed):
            return
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-API-Key, X-VG-Access-Key",
        )

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
                    "auth": (
                        "access_key"
                        if (config.access_key or "").strip()
                        else "open"
                    ),
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
        except _PayloadTooLarge as exc:
            self.close_connection = True
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": str(exc)})
            return
        except ValueError as exc:
            self.close_connection = True
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

        if body_size < 0:
            # read(-1) would block until EOF — never trust a negative length.
            raise ValueError("Invalid Content-Length.")

        if body_size > config.max_body_bytes:
            raise _PayloadTooLarge(
                f"Request body too large (max {config.max_body_bytes} bytes)."
            )

        try:
            raw_body = self.rfile.read(body_size)
        except (TimeoutError, OSError) as exc:
            raise ValueError("Request timed out while reading the body.") from exc

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
        extra_headers: dict[str, str] = {}
        if file_path.name == "index.html":
            body, policy = self._index_html()
            extra_headers["Content-Security-Policy"] = policy
        else:
            body = file_path.read_bytes()

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for name, value in extra_headers.items():
            self.send_header(name, value)
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _index_html(self) -> tuple[bytes, str]:
        """Render the UI with a per-response CSP nonce.

        The page ships one inline script and three pinned CDN scripts. The
        inline script gets a fresh nonce on every response so a Content
        Security Policy can allow it without allowing arbitrary inline code.
        """
        nonce = secrets.token_urlsafe(16)
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        html = html.replace('nonce="__VG_NONCE__"', f'nonce="{nonce}"')
        policy = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "base-uri 'none'; "
            "form-action 'self'; "
            "frame-ancestors 'none'"
        )
        return html.encode("utf-8"), policy

    def _send_json(
        self,
        status: HTTPStatus,
        payload: dict[str, Any],
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    # ─── Access control ─────────────────────────────────────────────
    def _client_id(self) -> str:
        """Identify the caller for rate limiting.

        The socket address is used rather than ``X-Forwarded-For`` because a
        forwarded header is trivially spoofed.
        """
        return self.client_address[0] if self.client_address else "unknown"

    def _access_key_configured(self) -> bool:
        return bool((config.access_key or "").strip())

    def _access_key_valid(self) -> bool:
        """Constant-time check of the deployment access key."""
        expected = (config.access_key or "").strip()
        submitted = self.headers.get("X-VG-Access-Key", "").strip()
        if not expected or not submitted:
            return False
        return hmac.compare_digest(submitted, expected)

    def _submitted_groq_key(self) -> str:
        """The caller's own Groq key (BYOK) — never the server's."""
        return self.headers.get("X-API-Key", "").strip()

    def _synthesis_key(self) -> str:
        """The key used for the single synthesis call.

        The caller's own key is always preferred. The server's key is only
        reachable by a request that passed the deployment access key, so an
        anonymous caller can never spend the operator's Groq quota.
        """
        caller_key = self._submitted_groq_key()
        if caller_key:
            return caller_key
        if self._access_key_configured() and self._access_key_valid():
            return config.groq_api_key or os.getenv("GROQ_API_KEY") or ""
        return ""

    def _check_access(self) -> bool:
        """Rate-limit the request, then enforce the deployment access key.

        Returns False — after sending the error response — when the request
        must not proceed.
        """
        if not _rate_limiter.allow(
            self._client_id(), limit=config.rate_limit_per_minute
        ):
            self._send_json(
                HTTPStatus.TOO_MANY_REQUESTS,
                {"error": "Too many requests. Try again in a minute."},
                extra_headers={"Retry-After": "60"},
            )
            return False

        if self._access_key_configured() and not self._access_key_valid():
            self._send_json(
                HTTPStatus.UNAUTHORIZED,
                {
                    "error": "Access key required.",
                    "hint": "Send the deployment key in X-VG-Access-Key.",
                },
            )
            return False

        return True

    def _handle_incident_investigate(self, body: dict[str, Any]) -> None:
        """POST /api/incident-investigate — question-driven mini CID investigation.

        Returns structured findings with provenance tags (documented,
        reported_unconfirmed, inferred, speculative), contradictions, and synthesis.
        """
        if not self._check_access():
            return

        question = str(body.get("question", "") or "").strip()

        if not question:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Question is required."})
            return

        if len(question) > config.max_question_chars:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error": (
                        f"Question is too long "
                        f"(max {config.max_question_chars} characters)."
                    )
                },
            )
            return

        try:
            # The caller's key drives the synthesis (BYOK); the server's own
            # GROQ_API_KEY is only reachable behind the deployment access key.
            result = investigate(
                question,
                api_key=self._synthesis_key(),
                deadline_seconds=config.max_investigation_seconds,
            )
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
    if config.access_key:
        print("  Access: deployment key required (X-VG-Access-Key)")
        print(
            "  Server fallback key: ✓ configured (synthesis for authorized callers)"
            if server_key
            else "  Server fallback key: ✗ not set (mechanical synthesis only)"
        )
    else:
        print("  Access: open (rate-limited)")
        print("  Server fallback key: ✗ not used — set VG_ACCESS_KEY to enable it")
    print(
        f"  Rate limit: {config.rate_limit_per_minute} investigations/minute per client"
    )

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
