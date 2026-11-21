import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Keep the per-client rate limit from leaking between tests."""
    from vg.api.server import _auth_limiter, _rate_limiter

    _rate_limiter.reset()
    _auth_limiter.reset()
    yield
    _rate_limiter.reset()
    _auth_limiter.reset()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Fail loudly if a test ever opens a socket.

    The investigator's sources are all keyless public APIs, so a test that
    reaches the network is slow, flaky and a privacy leak. Every source is
    gated by ``_IN_TEST``; this tripwire makes sure a new one cannot
    quietly forget the gate.
    """
    def refuse(*args, **kwargs):
        raise RuntimeError(
            "Network access is not allowed in tests — the source is missing "
            "its _IN_TEST gate."
        )

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    yield
