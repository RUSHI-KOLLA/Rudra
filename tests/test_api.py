#!/usr/bin/env python3
"""Integration tests for API endpoints."""

import sys
import json
import io
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

from vg.config import config
from vg.api.server import VGWebHandler
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

import pytest


class MockConnection:
    """Mock socket connection with makefile support."""
    def __init__(self, body=b""):
        self._body = body
        self._rbufsize = -1
        self._wbufsize = 0
        self._wfile = io.BytesIO()
        self._wfile.write = MagicMock()

    def makefile(self, mode, bufsize=-1):
        if 'r' in mode:
            return io.BytesIO(self._body)
        return self._wfile

    def sendall(self, data):
        pass

    def close(self):
        pass


def create_mock_handler(headers=None, body=None):
    """Create a VGWebHandler instance with fully mocked connection."""
    if body is not None and isinstance(body, dict):
        body_bytes = json.dumps(body).encode()
    elif isinstance(body, bytes):
        body_bytes = body
    elif body is None:
        body_bytes = b""
    else:
        body_bytes = str(body).encode()
    conn = MockConnection(body_bytes)

    # Create handler without calling setup()
    handler = BaseHTTPRequestHandler.__new__(VGWebHandler)
    handler.client_address = ("127.0.0.1", 8080)
    handler.server = MagicMock()
    handler.server.server_version = "VGWeb/2.0"
    handler.request = conn
    handler.headers = headers or {}
    handler.rfile = conn.makefile('rb')
    handler.wfile = conn.makefile('wb')

    # Mock response methods
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.log_message = MagicMock()

    return handler


class TestIncidentInvestigateEndpoint:
    """Tests for POST /api/incident-investigate endpoint."""

    def test_open_mode_serves_a_request_without_any_key(self):
        """Open mode (no deployment access key): the endpoint needs no key.

        Every source is keyless, so an investigation must work for an
        anonymous caller — with the deterministic mechanical synthesis.
        """
        handler = create_mock_handler(
            headers={"Content-Type": "application/json"},
            body=json.dumps({"question": "Why did the CEO resign?"}).encode()
        )
        handler._handle_incident_investigate({"question": "Why did the CEO resign?"})

        assert handler.send_response.call_args[0][0] == HTTPStatus.OK
        data = json.loads(handler.wfile.write.call_args[0][0].decode())
        assert data["synthesis"]

    def test_400_on_missing_question(self):
        """POST /api/incident-investigate returns 400 on missing/empty question."""
        handler = create_mock_handler(
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            body=json.dumps({"question": ""}).encode()
        )
        handler._handle_incident_investigate({"question": ""})

        assert handler.send_response.call_args[0][0] == HTTPStatus.BAD_REQUEST
        response_body = handler.wfile.write.call_args[0][0]
        data = json.loads(response_body.decode())
        assert "Question is required" in data["error"]

    def test_200_returns_structured_investigation(self):
        """POST /api/incident-investigate returns 200 with all required fields."""
        handler = create_mock_handler(
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            body=json.dumps({"question": "Why did Chanda Kochhar resign?"}).encode()
        )
        handler._handle_incident_investigate({"question": "Why did Chanda Kochhar resign?"})

        assert handler.send_response.call_args[0][0] == HTTPStatus.OK
        response_body = handler.wfile.write.call_args[0][0]
        data = json.loads(response_body.decode())

        # Verify top-level structure
        assert data["question"] == "Why did Chanda Kochhar resign?"
        assert "lens_results" in data
        assert "contradictions" in data
        assert "synthesis" in data
        assert "provenance" in data
        assert "question_profile" in data

        # Verify 6 lenses
        lenses = set(data["lens_results"].keys())
        expected_lenses = {"money", "power", "secrecy", "timing", "network", "counter_case"}
        assert lenses == expected_lenses

        # Verify contradictions is a list
        assert isinstance(data["contradictions"], list)

        # Verify synthesis is a string
        assert isinstance(data["synthesis"], str)
        assert len(data["synthesis"]) > 0

        # Verify provenance
        prov = data["provenance"]
        assert "total_findings" in prov
        assert "unique_sources" in prov
        assert "tag_counts" in prov
        assert "lenses_run" in prov
        assert set(prov["lenses_run"]) == expected_lenses

    def test_each_lens_has_queries_and_findings(self):
        """Each lens result has queries and findings lists."""
        handler = create_mock_handler(
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            body=json.dumps({"question": "Why did the CEO resign?"}).encode()
        )
        handler._handle_incident_investigate({"question": "Why did the CEO resign?"})

        response_body = handler.wfile.write.call_args[0][0]
        data = json.loads(response_body.decode())

        for lens_name, lens_data in data["lens_results"].items():
            assert "queries" in lens_data, f"{lens_name} missing 'queries'"
            assert "findings" in lens_data, f"{lens_name} missing 'findings'"
            assert isinstance(lens_data["queries"], list)
            assert isinstance(lens_data["findings"], list)

    def test_findings_have_provenance_tags(self):
        """Every finding has a valid provenance tag."""
        handler = create_mock_handler(
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            body=json.dumps({"question": "Why did the CEO resign?"}).encode()
        )
        handler._handle_incident_investigate({"question": "Why did the CEO resign?"})

        response_body = handler.wfile.write.call_args[0][0]
        data = json.loads(response_body.decode())

        valid_tags = {"documented", "reported_unconfirmed", "inferred", "speculative"}
        for lens_name, lens_data in data["lens_results"].items():
            for finding in lens_data["findings"]:
                assert "tag" in finding, f"{lens_name} finding missing 'tag'"
                assert finding["tag"] in valid_tags, \
                    f"{lens_name} finding has invalid tag: {finding['tag']}"


class TestOnlyInvestigateIsServed:
    """The server exposes exactly one analysis endpoint: the investigator."""

    def test_analyze_endpoint_is_gone(self):
        """POST /api/analyze returns 404 — the debate pipeline is removed."""
        handler = create_mock_handler(
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            body=json.dumps({"question": "Why did the CEO resign?"}).encode(),
        )
        handler.path = "/api/analyze"
        handler.do_POST()

        assert handler.send_response.call_args[0][0] == HTTPStatus.NOT_FOUND

    def test_incident_match_endpoint_is_gone(self):
        """POST /api/incident-match returns 404 — the paste-a-case flow is removed."""
        handler = create_mock_handler(
            headers={"Content-Type": "application/json", "X-API-Key": "test-key"},
            body=json.dumps({"paste": "some incident text"}).encode(),
        )
        handler.path = "/api/incident-match"
        handler.do_POST()

        assert handler.send_response.call_args[0][0] == HTTPStatus.NOT_FOUND

    def test_health_lists_only_investigate(self):
        """GET /api/health reports the investigator as the only mode."""
        handler = create_mock_handler(headers={})
        handler.path = "/api/health"
        handler.do_GET()

        assert handler.send_response.call_args[0][0] == HTTPStatus.OK
        data = json.loads(handler.wfile.write.call_args[0][0].decode())
        assert data["modes"] == ["investigate"]
        assert "debate_enabled" not in data

    def test_health_reports_open_mode_for_a_blank_access_key(self, monkeypatch):
        """A whitespace-only key is not a key — health must not claim otherwise.

        The UI decides whether to show the access-key field from this
        field, so it has to agree with what the request path enforces.
        """
        monkeypatch.setattr(config, "access_key", "   ")
        handler = create_mock_handler(headers={})
        handler.path = "/api/health"
        handler.do_GET()

        data = json.loads(handler.wfile.write.call_args[0][0].decode())
        assert data["auth"] == "open"


class TestConfigIsForgiving:
    """A typo in an environment variable must not take the service down."""

    def test_a_non_numeric_limit_falls_back_to_the_default(self, monkeypatch):
        from vg.config import _env_int

        monkeypatch.setenv("VG_RATE_LIMIT_PER_MINUTE", "ten")
        assert _env_int("VG_RATE_LIMIT_PER_MINUTE", 10) == 10

    def test_a_numeric_limit_is_used(self, monkeypatch):
        from vg.config import _env_int

        monkeypatch.setenv("VG_RATE_LIMIT_PER_MINUTE", "3")
        assert _env_int("VG_RATE_LIMIT_PER_MINUTE", 10) == 3

    def test_an_unset_limit_falls_back_to_the_default(self, monkeypatch):
        from vg.config import _env_int

        monkeypatch.delenv("VG_RATE_LIMIT_PER_MINUTE", raising=False)
        assert _env_int("VG_RATE_LIMIT_PER_MINUTE", 10) == 10


class TestInvestigateOnlyUI:
    """The browser UI exposes exactly one flow: the investigator."""

    @staticmethod
    def _html() -> str:
        path = Path(__file__).resolve().parents[1] / "vg" / "api" / "static" / "index.html"
        return path.read_text()

    def test_static_ui_has_no_debate_or_match_calls(self):
        """The removed endpoints are not called from the browser UI."""
        html = self._html()
        assert "/api/analyze" not in html
        assert "/api/incident-match" not in html

    def test_static_ui_calls_the_investigator(self):
        """The investigator endpoint is wired into the UI."""
        assert "/api/incident-investigate" in self._html()

    def test_static_ui_has_no_incident_mode_button(self):
        """The paste-a-case mode button is gone."""
        assert 'data-mode="incident"' not in self._html()


class TestAccessControlAndBudgets:
    """The endpoint must never let anonymous callers spend the server's quota.

    Contract:
      - open mode (no VG_ACCESS_KEY): no key needed; the server's Groq key
        is never used for synthesis.
      - access-key mode (VG_ACCESS_KEY set): X-VG-Access-Key required (401),
        and only then may the server's Groq key be used.
      - budgets: body size, question length, and a per-client rate limit.
    """

    @pytest.fixture(autouse=True)
    def _isolated(self, monkeypatch):
        from vg.api.server import _rate_limiter

        monkeypatch.setattr(config, "access_key", None)
        monkeypatch.setattr(config, "groq_api_key", None)
        monkeypatch.setattr(config, "rate_limit_per_minute", 10)
        monkeypatch.setattr(config, "max_question_chars", 500)
        monkeypatch.setattr(config, "max_body_bytes", 65536)
        _rate_limiter.reset()
        yield
        _rate_limiter.reset()

    @staticmethod
    def _capture_investigate(monkeypatch) -> dict:
        """Replace the pipeline with a recorder and return the captured calls."""
        from vg.api import server as server_mod

        seen: dict = {}

        def fake_investigate(question, api_key=None, deadline_seconds=None):
            seen["question"] = question
            seen["api_key"] = api_key
            seen["deadline_seconds"] = deadline_seconds
            return {
                "question": question,
                "lens_results": {},
                "question_profile": {},
                "synthesis": "mechanical summary",
                "provenance": {
                    "total_findings": 0,
                    "unique_sources": 0,
                    "tag_counts": {},
                    "lenses_run": [],
                },
                "contradictions": [],
            }

        monkeypatch.setattr(server_mod, "investigate", fake_investigate)
        return seen

    def test_open_mode_never_spends_the_server_groq_key(self, monkeypatch):
        """A server-side Groq key must not pay for anonymous callers."""
        monkeypatch.setattr(config, "groq_api_key", "server-side-secret")
        seen = self._capture_investigate(monkeypatch)

        handler = create_mock_handler(headers={}, body=b"{}")
        handler._handle_incident_investigate({"question": "Why did the CEO resign?"})

        assert handler.send_response.call_args[0][0] == HTTPStatus.OK
        assert seen["api_key"] in (None, ""), seen["api_key"]

    def test_caller_key_is_used_for_synthesis(self, monkeypatch):
        """The caller's own key (BYOK) drives the synthesis call."""
        seen = self._capture_investigate(monkeypatch)

        handler = create_mock_handler(
            headers={"X-API-Key": "caller-key"}, body=b"{}"
        )
        handler._handle_incident_investigate({"question": "Why did the CEO resign?"})

        assert seen["api_key"] == "caller-key"

    def test_access_key_mode_rejects_a_missing_access_key(self, monkeypatch):
        """With VG_ACCESS_KEY set, a request without it is 401."""
        monkeypatch.setattr(config, "access_key", "deployment-secret")
        self._capture_investigate(monkeypatch)

        handler = create_mock_handler(
            headers={"X-API-Key": "caller-key"}, body=b"{}"
        )
        handler._handle_incident_investigate({"question": "Why did the CEO resign?"})

        assert handler.send_response.call_args[0][0] == HTTPStatus.UNAUTHORIZED
        data = json.loads(handler.wfile.write.call_args[0][0].decode())
        assert "Access key" in data["error"]

    def test_access_key_mode_rejects_a_wrong_access_key(self, monkeypatch):
        """A wrong access key is 401, even with a valid caller key."""
        monkeypatch.setattr(config, "access_key", "deployment-secret")
        self._capture_investigate(monkeypatch)

        handler = create_mock_handler(
            headers={"X-VG-Access-Key": "wrong", "X-API-Key": "caller-key"},
            body=b"{}",
        )
        handler._handle_incident_investigate({"question": "Why did the CEO resign?"})

        assert handler.send_response.call_args[0][0] == HTTPStatus.UNAUTHORIZED

    def test_access_key_mode_allows_the_server_key_for_authorized_callers(self, monkeypatch):
        """An authorized caller may spend the server's quota."""
        monkeypatch.setattr(config, "access_key", "deployment-secret")
        monkeypatch.setattr(config, "groq_api_key", "server-side-secret")
        seen = self._capture_investigate(monkeypatch)

        handler = create_mock_handler(
            headers={"X-VG-Access-Key": "deployment-secret"}, body=b"{}"
        )
        handler._handle_incident_investigate({"question": "Why did the CEO resign?"})

        assert handler.send_response.call_args[0][0] == HTTPStatus.OK
        assert seen["api_key"] == "server-side-secret"

    def test_caller_key_wins_over_the_server_key(self, monkeypatch):
        """A caller-supplied key is preferred over the server's key."""
        monkeypatch.setattr(config, "access_key", "deployment-secret")
        monkeypatch.setattr(config, "groq_api_key", "server-side-secret")
        seen = self._capture_investigate(monkeypatch)

        handler = create_mock_handler(
            headers={"X-VG-Access-Key": "deployment-secret", "X-API-Key": "caller-key"},
            body=b"{}",
        )
        handler._handle_incident_investigate({"question": "Why did the CEO resign?"})

        assert seen["api_key"] == "caller-key"

    def test_oversized_body_is_rejected_with_413(self):
        """A body larger than the limit is refused before it is read."""
        handler = create_mock_handler(
            headers={"Content-Type": "application/json", "Content-Length": "999999"},
            body=b"",
        )
        handler.path = "/api/incident-investigate"
        handler.do_POST()

        assert handler.send_response.call_args[0][0] == HTTPStatus.REQUEST_ENTITY_TOO_LARGE

    def test_negative_content_length_is_rejected_with_400(self):
        """A negative Content-Length must not turn into an unbounded read."""
        handler = create_mock_handler(
            headers={"Content-Type": "application/json", "Content-Length": "-1"},
            body=b"",
        )
        handler.path = "/api/incident-investigate"
        handler.do_POST()

        assert handler.send_response.call_args[0][0] == HTTPStatus.BAD_REQUEST
        data = json.loads(handler.wfile.write.call_args[0][0].decode())
        assert data["error"] == "Invalid Content-Length."

    def test_oversized_question_is_rejected_with_400(self):
        """A question beyond the character limit is refused."""
        handler = create_mock_handler(headers={}, body=b"{}")
        handler._handle_incident_investigate({"question": "x" * 1000})

        assert handler.send_response.call_args[0][0] == HTTPStatus.BAD_REQUEST
        data = json.loads(handler.wfile.write.call_args[0][0].decode())
        assert "too long" in data["error"].lower()

    def test_rate_limited_requests_get_429(self, monkeypatch):
        """A client that exceeds the per-minute budget is refused with 429."""
        monkeypatch.setattr(config, "rate_limit_per_minute", 2)
        self._capture_investigate(monkeypatch)

        statuses = []
        for _ in range(3):
            handler = create_mock_handler(headers={}, body=b"{}")
            handler._handle_incident_investigate({"question": "Why did the CEO resign?"})
            statuses.append(handler.send_response.call_args[0][0])

        assert statuses[:2] == [HTTPStatus.OK, HTTPStatus.OK]
        assert statuses[2] == HTTPStatus.TOO_MANY_REQUESTS

    def test_cors_is_not_wildcard(self):
        """A wildcard CORS origin would let any site drive the endpoint."""
        handler = create_mock_handler(
            headers={"Origin": "https://evil.example"}, body=b"{}"
        )
        handler.path = "/api/health"
        handler.do_GET()

        sent = {
            call.args[0]: call.args[1]
            for call in handler.send_header.call_args_list
            if len(call.args) == 2
        }
        assert "Access-Control-Allow-Origin" not in sent

    def test_cors_allows_a_configured_origin(self, monkeypatch):
        """An explicitly allowed origin is echoed back."""
        monkeypatch.setattr(config, "allowed_origins", ("https://app.example",))
        handler = create_mock_handler(
            headers={"Origin": "https://app.example"}, body=b"{}"
        )
        handler.path = "/api/health"
        handler.do_GET()

        sent = {
            call.args[0]: call.args[1]
            for call in handler.send_header.call_args_list
            if len(call.args) == 2
        }
        assert sent.get("Access-Control-Allow-Origin") == "https://app.example"


class TestBrowserHardening:
    """The UI must not hand its secrets to a compromised dependency."""

    @staticmethod
    def _html() -> str:
        path = Path(__file__).resolve().parents[1] / "vg" / "api" / "static" / "index.html"
        return path.read_text()

    def test_cdn_scripts_are_integrity_pinned(self):
        """Every remote script carries a subresource-integrity hash."""
        import re

        html = self._html()
        remote_scripts = re.findall(r'<script[^>]*src="https://[^"]+"[^>]*>', html)
        assert remote_scripts, "expected the UI to load pinned CDN scripts"
        for tag in remote_scripts:
            assert "integrity=\"sha384-" in tag, tag
            assert "crossorigin=\"anonymous\"" in tag, tag

    def test_inline_script_carries_a_nonce_placeholder(self):
        """The inline script is marked for the per-response CSP nonce."""
        import re

        html = self._html()
        inline = re.findall(r"<script(?![^>]*src=)[^>]*>", html)
        assert inline, "expected an inline script"
        for tag in inline:
            assert 'nonce="__VG_NONCE__"' in tag, tag

    def test_index_is_served_with_a_content_security_policy(self):
        """The page is served with a CSP that pins script sources."""
        handler = create_mock_handler(headers={})
        handler.path = "/"
        handler.do_GET()

        sent = {
            call.args[0]: call.args[1]
            for call in handler.send_header.call_args_list
            if len(call.args) == 2
        }
        policy = sent.get("Content-Security-Policy", "")
        assert "script-src" in policy, policy
        assert "nonce-" in policy, policy
        assert "frame-ancestors 'none'" in policy, policy

    def test_the_inline_script_carries_the_served_nonce(self):
        """The nonce in the policy must match the one in the page, or the
        browser blocks the page's own script."""
        import re

        handler = create_mock_handler(headers={})
        handler.path = "/"
        handler.do_GET()

        sent = {
            call.args[0]: call.args[1]
            for call in handler.send_header.call_args_list
            if len(call.args) == 2
        }
        policy = sent.get("Content-Security-Policy", "")
        nonce = re.search(r"'nonce-([^']+)'", policy)
        assert nonce, policy

        body = handler.wfile.write.call_args[0][0].decode("utf-8")
        assert f'nonce="{nonce.group(1)}"' in body
        assert "__VG_NONCE__" not in body

    def test_api_key_is_not_kept_in_local_storage(self):
        """A long-lived secret must not sit in localStorage for the whole browser."""
        html = self._html()
        assert "localStorage.setItem('vg_api_key'" not in html
        assert "sessionStorage" in html

    def test_no_inline_event_handlers(self):
        """Inline handlers are blocked by the CSP, so there must be none."""
        import re

        html = self._html()
        handlers = re.findall(r'\son[a-z]+="[^"]*"', html)
        assert not handlers, handlers

    def test_client_checks_the_link_scheme(self):
        """The client refuses to render a link with a non-http scheme."""
        html = self._html()
        assert "http://" in html and "https://" in html
        assert "safeUrl" in html or "safeURL" in html

    def test_the_api_key_is_optional_in_the_setup_overlay(self):
        """A visitor can investigate without a key of their own."""
        html = self._html()
        assert 'id="setup-api-key"' in html
        key_input = html.split('id="setup-api-key"', 1)[1].split(">", 1)[0]
        assert "required" not in key_input, key_input
        assert "skip" in html.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
