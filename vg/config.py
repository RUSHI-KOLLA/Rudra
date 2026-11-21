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

    # --- Model Selection ---
    model_large: str = "openai/gpt-oss-120b"

    # --- Generation ---
    temperature: float = 0.2
    max_tokens: int = 1500


def get_config() -> Config:
    """Build config from environment."""
    return Config(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_large=os.getenv("GROQ_MODEL_LARGE", "openai/gpt-oss-120b"),
        temperature=float(os.getenv("VG_TEMPERATURE", "0.2")),
        max_tokens=int(os.getenv("VG_MAX_TOKENS", "1500")),
    )


config = get_config()
