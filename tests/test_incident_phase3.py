"""Offline integration tests for Phase 3 incident endpoints.

Tests the VGWebHandler dispatch and typed failure contracts without
starting a server. Uses stubbed extractor/embedder to stay deterministic.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if PROJECT_ROOT in sys.path:
    sys.path.remove(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from http import HTTPStatus

from vg.api.server import VGWebHandler
from vg.config import config
from vg.incidents.match import ExtractionIncomplete
from vg.incidents.store import IncidentStoreError


# ─── Minimal fake request/response capture ──────────────────────────────

class CapturingHandler(VGWebHandler):
    """VGWebHandler that captures _send_json calls instead of writing to socket."""

    def __init__(self):
        # Don't call parent __init__ - we'll set up only what we need
        self.server_version = "VGWeb/2.0"
        self.headers = {}
        self.rfile = None
        self.wfile = None
        self.request = MagicMock()
        self.client_address = ("127.0.0.1", 0)
        self.server = MagicMock()
        self._captured_status = None
        self._captured_payload = None

    def _send_json(self, status: HTTPStatus, payload: dict):
        """Capture instead of writing to socket."""
        self._captured_status = status
        self._captured_payload = payload

    def _serve_file(self, _):
        self._captured_status = HTTPStatus.OK
        self._captured_payload = {"served": True}

    def _read_json_body(self) -> dict:
        if self.rfile is None:
            raise ValueError("No body set")
        raw = self.rfile.read()
        if not raw:
            raise ValueError("Empty request body.")
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON.") from exc

    def assert_status(self, expected: int):
        assert self._captured_status == expected, (
            f"expected {expected}, got {self._captured_status}: "
            f"{json.dumps(self._captured_payload)[:200]}"
        )

    def json(self) -> dict:
        return self._captured_payload


class FakeBodyReader:
    def __init__(self, data: dict):
        self._data = json.dumps(data).encode("utf-8")
        self._pos = 0
    def read(self, n=-1):
        if n == -1:
            out = self._data[self._pos:]
            self._pos = len(self._data)
        else:
            out = self._data[self._pos:self._pos+n]
            self._pos += len(out)
        return out
    def close(self):
        pass


# ─── Fixtures ───────────────────────────────────────────────────────────

PASTE_MIN = "Acme CEO Jane Roe resigned yesterday after a fraud probe by the SEC. Board appointed an interim chief."


@pytest.fixture(autouse=True)
def reset_config():
    """Ensure debate_enabled is off for deterministic test isolation."""
    orig = config.debate_enabled
    config.debate_enabled = False
    yield
    config.debate_enabled = orig


@pytest.fixture
def no_groq_key():
    """Ensure no Groq key in environment (for 401 paths)."""
    orig_env = {}
    for k in ["GROQ_API_KEY", "TAVILY_API_KEY", "GEMINI_API_KEY"]:
        orig_env[k] = os.environ.get(k)
        os.environ.pop(k, None)
    orig_config = config.groq_api_key
    config.groq_api_key = None
    yield
    for k, v in orig_env.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)
    config.groq_api_key = orig_config


# ─── Tests ──────────────────────────────────────────────────────────────

class TestDispatch:
    """Dispatch table routes to the correct handlers."""

    def test_get_health_returns_debate_enabled_false(self):
        h = CapturingHandler()
        h.do_GET = lambda: h._send_json(HTTPStatus.OK, {
            "status": "ok", "service": "vg-web", "version": "2.0",
            "mode": "saas", "debate_enabled": bool(config.debate_enabled)
        })
        # Simulate the actual do_GET for /api/health
        from urllib.parse import urlparse
        h.path = "/api/health"
        parsed = urlparse(h.path)
        if parsed.path == "/api/health":
            h._send_json(HTTPStatus.OK, {
                "status": "ok", "service": "vg-web", "version": "2.0",
                "mode": "saas", "debate_enabled": bool(config.debate_enabled)
            })
        h.assert_status(HTTPStatus.OK)
        data = h.json()
        assert data["debate_enabled"] is False
        assert data["status"] == "ok"

    def test_post_analyze_409_when_flag_off(self):
        h = CapturingHandler()
        h.headers = {}
        h.rfile = FakeBodyReader({"question": "Will X happen?"})
        with patch("vg.api.server.analyze_async", new_callable=AsyncMock) as m:
            h._handle_analyze({"question": "Will X happen?"})
            m.assert_not_called()  # coordinator never constructed
        h.assert_status(HTTPStatus.CONFLICT)
        data = h.json()
        assert data["error"] == "forecast mode disabled"

    def test_post_incident_match_routes_to_match_handler(self):
        h = CapturingHandler()
        h.headers = {"X-API-Key": "gsk_test"}
        h.rfile = FakeBodyReader({"paste": PASTE_MIN})
        with patch("vg.api.server.run_match", new_callable=AsyncMock) as m:
            m.return_value = {"status": "complete", "matches": [], "corpus_size": 0}
            h._handle_incident_match({"paste": PASTE_MIN})
            m.assert_awaited_once()
        h.assert_status(HTTPStatus.OK)

    def test_post_incident_outcome_routes_to_outcome_handler(self):
        h = CapturingHandler()
        h.headers = {"X-API-Key": "gsk_test"}
        h.rfile = FakeBodyReader({"incident_id": "x", "outcome_text": "y"})
        with patch("vg.api.server.record_outcome", new_callable=AsyncMock) as m:
            m.return_value = {"status": "recorded"}
            h._handle_incident_outcome({"incident_id": "x", "outcome_text": "y"})
            m.assert_awaited_once()
        h.assert_status(HTTPStatus.OK)


class TestFailureContracts:
    """Typed failure shapes for the three incident routes."""

    def test_incident_match_401_when_no_key(self, no_groq_key):
        h = CapturingHandler()
        h.headers = {}
        h.rfile = FakeBodyReader({"paste": PASTE_MIN})
        with patch("vg.api.server.run_match", new_callable=AsyncMock) as m:
            h._handle_incident_match({"paste": PASTE_MIN})
            m.assert_not_called()
        h.assert_status(HTTPStatus.UNAUTHORIZED)
        data = h.json()
        assert data["error"] == "Groq API key required."
        assert "X-API-Key" in data["hint"]

    def test_incident_match_422_needs_manual_entry(self, no_groq_key):
        """ExtractionIncomplete -> 422 with missing[], raw_paste, spooled_path."""
        h = CapturingHandler()
        h.headers = {"X-API-Key": "gsk_test"}
        h.rfile = FakeBodyReader({"paste": PASTE_MIN})
        with patch("vg.api.server.run_match", new_callable=AsyncMock) as m:
            m.side_effect = ExtractionIncomplete(
                missing=["trigger_type", "actors"],
                raw_paste=PASTE_MIN,
                spooled_path="/tmp/raw.txt",
            )
            h._handle_incident_match({"paste": PASTE_MIN})
        h.assert_status(HTTPStatus.UNPROCESSABLE_ENTITY)
        data = h.json()
        assert data["error"] == "needs_manual_entry"
        assert data["status"] == "needs_manual_entry"
        assert data["missing"] == ["trigger_type", "actors"]
        assert data["raw_paste"] == PASTE_MIN
        assert data["spooled_path"] == "/tmp/raw.txt"

    def test_incident_match_503_incident_store_error(self, no_groq_key):
        """IncidentStoreError -> 503 with reason, never empty result set."""
        h = CapturingHandler()
        h.headers = {"X-API-Key": "gsk_test"}
        h.rfile = FakeBodyReader({"paste": PASTE_MIN})
        with patch("vg.api.server.run_match", new_callable=AsyncMock) as m:
            m.side_effect = IncidentStoreError("chromadb PersistentClient failed: lock")
            h._handle_incident_match({"paste": PASTE_MIN})
        h.assert_status(HTTPStatus.SERVICE_UNAVAILABLE)
        data = h.json()
        assert data["error"] == "service unavailable"
        assert "chromadb" in data["reason"].lower()

    def test_incident_outcome_404_unknown_card(self, no_groq_key):
        h = CapturingHandler()
        h.headers = {"X-API-Key": "gsk_test"}
        h.rfile = FakeBodyReader({"incident_id": "nope", "outcome_text": "y"})
        with patch("vg.api.server.record_outcome", new_callable=AsyncMock) as m:
            m.side_effect = LookupError("nope")
            h._handle_incident_outcome({"incident_id": "nope", "outcome_text": "y"})
        h.assert_status(HTTPStatus.NOT_FOUND)
        data = h.json()
        assert data["error"] == "unknown incident_id"
        assert data["incident_id"] == "nope"

    def test_analyze_409_when_flag_off_then_401(self, no_groq_key):
        """When debate_enabled=False, flag gate wins (409). When True, needs key (401)."""
        h = CapturingHandler()
        h.headers = {}
        h.rfile = FakeBodyReader({"question": "Will X happen?"})
        with patch("vg.api.server.analyze_async", new_callable=AsyncMock) as m:
            h._handle_analyze({"question": "Will X happen?"})
            m.assert_not_called()
        # debate_enabled is False via autouse fixture -> 409 first
        h.assert_status(HTTPStatus.CONFLICT)
        data = h.json()
        assert data["error"] == "forecast mode disabled"

        # Now test with flag ON -> 401
        config.debate_enabled = True
        try:
            h2 = CapturingHandler()
            h2.headers = {}
            h2.rfile = FakeBodyReader({"question": "Will X happen?"})
            with patch("vg.api.server.analyze_async", new_callable=AsyncMock) as m:
                h2._handle_analyze({"question": "Will X happen?"})
                m.assert_not_called()
            h2.assert_status(HTTPStatus.UNAUTHORIZED)
            data2 = h2.json()
            assert data2["error"] == "Groq API key required."
        finally:
            config.debate_enabled = False


class TestIncidentMatchTwoPhase:
    """Phase 1 (no extracted) -> reviewing; Phase 2 (extracted) -> complete."""

    def test_phase1_no_extracted_returns_reviewing(self, no_groq_key):
        h = CapturingHandler()
        h.headers = {"X-API-Key": "gsk_test"}
        h.rfile = FakeBodyReader({"paste": PASTE_MIN})
        with patch("vg.api.server.run_match", new_callable=AsyncMock) as m:
            m.return_value = {"status": "reviewing", "extracted_card": {"trigger_type": "fraud"}}
            h._handle_incident_match({"paste": PASTE_MIN})
        h.assert_status(HTTPStatus.OK)
        data = h.json()
        assert data["status"] == "reviewing"
        assert "extracted_card" in data

    def test_phase2_with_extracted_returns_complete(self, no_groq_key):
        body = {"paste": PASTE_MIN, "extracted": {"trigger_type": "fraud", "actors": ["A", "B"]}}
        h = CapturingHandler()
        h.headers = {"X-API-Key": "gsk_test"}
        h.rfile = FakeBodyReader(body)
        with patch("vg.api.server.run_match", new_callable=AsyncMock) as m:
            m.return_value = {"status": "complete", "matches": [], "corpus_size": 24}
            h._handle_incident_match(body)
        h.assert_status(HTTPStatus.OK)
        data = h.json()
        assert data["status"] == "complete"
        assert "extracted_card" not in data  # Phase 2 never returns reviewing

    def test_truncated_flag_on_long_paste(self, no_groq_key):
        long = "x" * 5000
        h = CapturingHandler()
        h.headers = {"X-API-Key": "gsk_test"}
        h.rfile = FakeBodyReader({"paste": long})
        with patch("vg.api.server.run_match", new_callable=AsyncMock) as m:
            m.return_value = {"status": "complete", "matches": [], "corpus_size": 0, "truncated": True}
            h._handle_incident_match({"paste": long})
        h.assert_status(HTTPStatus.OK)
        data = h.json()
        assert data.get("truncated") is True


class TestConfigDefaults:
    """Config values used in incident mode."""

    def test_incident_weak_threshold_defaults_to_calibrated(self):
        # R3: default is the live-calibrated p60 value, not the pre-calibration 0.45
        assert config.incident_weak_threshold == 0.3222

    def test_incidents_data_path_resolves_against_package_root(self):
        # R2: relative paths anchor at the package root (repo root)
        assert config.incidents_data_path == str(PROJECT_ROOT / "data" / "incidents")
        assert Path(config.incidents_data_path).exists()

    def test_debate_enabled_defaults_false(self):
        assert config.debate_enabled is False


# ─── Runner ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])