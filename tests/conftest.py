import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Keep the per-client rate limit from leaking between tests."""
    from vg.api.server import _rate_limiter

    _rate_limiter.reset()
    yield
    _rate_limiter.reset()
