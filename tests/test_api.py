#!/usr/bin/env python3
"""Integration tests for API endpoints."""

import sys
import os
import json
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

from vg.config import config
from vg.api.server import VGWebHandler
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse


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

    def test_401_without_x_api_key(self):
        """POST /api/incident-investigate returns 401 without X-API-Key."""
        handler = create_mock_handler(
            headers={"Content-Type": "application/json"},
            body=json.dumps({"question": "Why did the CEO resign?"}).encode()
        )
        # No X-API-Key header
        handler._handle_incident_investigate({"question": "Why did the CEO resign?"})

        # Check 401 was sent
        assert handler.send_response.call_args[0][0] == HTTPStatus.UNAUTHORIZED
        response_body = handler.wfile.write.call_args[0][0]
        data = json.loads(response_body.decode())
        assert data["error"] == "Groq API key required."

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
