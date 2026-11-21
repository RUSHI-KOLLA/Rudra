"""VG Configuration — loads from .env or environment variables."""

from dataclasses import dataclass
from typing import Optional
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # --- API Keys (BYOK) ---
    #: Optional. When set, the investigator's synthesis uses one bounded
    #: Groq call. When unset, the mechanical summary is used.
    groq_api_key: Optional[str] = None

    #: Optional deployment secret. When set, every request to the
    #: investigator must present it in ``X-VG-Access-Key`` and the server's
    #: own Groq quota may be used for synthesis. When unset the endpoint is
    #: open (rate-limited) and the server's Groq key is never spent on
    #: anonymous callers.
    access_key: Optional[str] = None

    #: Origins allowed to call the API cross-origin. Empty means same-origin
    #: only, which is all the bundled browser UI needs.
    allowed_origins: tuple[str, ...] = ()

    # --- Request budgets ---
    #: Investigations allowed per minute per client address (0 = unlimited).
    rate_limit_per_minute: int = 10
    #: Longest accepted question, in characters.
    max_question_chars: int = 500
    #: Largest accepted request body, in bytes.
    max_body_bytes: int = 65536
    #: Wall-clock ceiling for one investigation.
    max_investigation_seconds: int = 60

    # --- Model Selection ---
    model_large: str = "openai/gpt-oss-120b"

    # --- Generation ---
    temperature: float = 0.2
    max_tokens: int = 1500


def _env_int(name: str, default: int) -> int:
    """Read an integer setting, falling back to the default.

    A typo in an environment variable must not take the whole service
    down at import time, so a bad value is ignored (and reported) rather
    than raised.
    """
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        print(f"[vg-config] {name}={raw!r} is not an integer — using {default}.")
        return default


def get_config() -> Config:
    """Build config from environment."""
    origins = tuple(
        origin.strip()
        for origin in os.getenv("VG_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    )
    return Config(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        access_key=os.getenv("VG_ACCESS_KEY"),
        allowed_origins=origins,
        rate_limit_per_minute=_env_int("VG_RATE_LIMIT_PER_MINUTE", 10),
        max_question_chars=_env_int("VG_MAX_QUESTION_CHARS", 500),
        max_body_bytes=_env_int("VG_MAX_BODY_BYTES", 65536),
        max_investigation_seconds=_env_int("VG_MAX_INVESTIGATION_SECONDS", 60),
        model_large=os.getenv("GROQ_MODEL_LARGE", "openai/gpt-oss-120b"),
        temperature=float(os.getenv("VG_TEMPERATURE", "0.2")),
        max_tokens=_env_int("VG_MAX_TOKENS", 1500),
    )


config = get_config()
