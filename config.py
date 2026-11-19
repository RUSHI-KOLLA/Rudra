"""VG Configuration — loads from .env or environment variables."""

from dataclasses import dataclass, field
from typing import Optional
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Package root: this file lives at the repo root, which IS the vg package.
_PACKAGE_ROOT = Path(__file__).resolve().parent


def _resolve_path(value: str, default_rel: str) -> str:
    """Resolve a possibly-relative path against the package root.

    Relative values are anchored at the package root, not the process CWD,
    so the data directory is the same directory whichever way the server is
    launched (``python -m vg.main`` from the parent, or from inside the repo).
    """
    raw = value or default_rel
    path = Path(raw)
    if not path.is_absolute():
        path = _PACKAGE_ROOT / path
    return str(path)


@dataclass
class Config:
    # --- API Keys (BYOK) ---
    groq_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

    # --- Model Selection ---
    model_large: str = "openai/gpt-oss-20b"
    model_small: str = "allam-2-7b"
    # Gemini 2.5 Flash with native context caching
    gemini_model: str = "gemini-2.0-flash"
    # Provider: 'gemini' or 'groq'
    default_provider: str = "groq"

    # --- Rate Limiting ---
    groq_rpm_limit: int = 15
    groq_max_concurrent: int = 5
    groq_request_timeout_seconds: int = 18
    groq_shadow_timeout_seconds: int = 12
    groq_max_retries: int = 2

    # --- Generation ---
    temperature: float = 0.7
    max_tokens: int = 2048
    shadow_max_tokens: int = 96
    agent_max_tokens: int = 640
    judge_max_tokens: int = 1024

    # --- RAG ---
    chroma_db_path: str = "./chroma_db"
    rag_top_k: int = 2          # chunks per personality
    rag_chunk_words: int = 300

    # --- Debate ---
    max_debate_rounds: int = 2
    convergence_threshold: float = 0.8   # 80% agreement → early exit
    judge_consistency_runs: int = 3

    # --- Incident mode ---
    incidents_data_path: str = ""
    incidents_collection: str = "incidents"
    incident_weak_threshold: float = 0.3222
    debate_enabled: bool = False
    max_research_rounds: int = 1
    questions_per_round: int = 5
    incidents_research_enabled: bool = False

    # --- Search ---
    disable_web_search: bool = False


def get_config() -> Config:
    """Build config from environment."""
    return Config(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        tavily_api_key=os.getenv("TAVILY_API_KEY"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        model_large=os.getenv("GROQ_MODEL_LARGE", "openai/gpt-oss-20b"),
        model_small=os.getenv("GROQ_MODEL_SMALL", "allam-2-7b"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        default_provider=os.getenv("LLM_PROVIDER", "groq"),
        groq_rpm_limit=int(os.getenv("GROQ_RPM_LIMIT", "15")),
        groq_max_concurrent=int(os.getenv("GROQ_MAX_CONCURRENT", "5")),
        groq_request_timeout_seconds=int(os.getenv("GROQ_REQUEST_TIMEOUT_SECONDS", "18")),
        groq_shadow_timeout_seconds=int(os.getenv("GROQ_SHADOW_TIMEOUT_SECONDS", "12")),
        groq_max_retries=int(os.getenv("GROQ_MAX_RETRIES", "2")),
        temperature=float(os.getenv("VG_TEMPERATURE", "0.7")),
        max_tokens=int(os.getenv("VG_MAX_TOKENS", "2048")),
        shadow_max_tokens=int(os.getenv("VG_SHADOW_MAX_TOKENS", "96")),
        agent_max_tokens=int(os.getenv("VG_AGENT_MAX_TOKENS", "640")),
        judge_max_tokens=int(os.getenv("VG_JUDGE_MAX_TOKENS", "1024")),
        chroma_db_path=_resolve_path(
            os.getenv("VG_CHROMA_PATH", ""), os.path.join("chroma_db")
        ),
        rag_top_k=int(os.getenv("VG_RAG_TOP_K", "2")),
        rag_chunk_words=int(os.getenv("VG_RAG_CHUNK_WORDS", "300")),
        max_debate_rounds=int(os.getenv("VG_MAX_DEBATE_ROUNDS", "2")),
        convergence_threshold=float(os.getenv("VG_CONVERGENCE_THRESHOLD", "0.8")),
        judge_consistency_runs=int(os.getenv("VG_JUDGE_CONSISTENCY_RUNS", "3")),
        incidents_data_path=_resolve_path(
            os.getenv("VG_INCIDENTS_DATA_PATH", ""),
            os.path.join("data", "incidents"),
        ),
        incidents_collection=os.getenv("VG_INCIDENTS_COLLECTION", "incidents"),
        incident_weak_threshold=float(
            os.getenv("VG_INCIDENT_WEAK_THRESHOLD", "0.3222")
        ),
        debate_enabled=os.getenv("VG_DEBATE_ENABLED", "").lower()
        in {"1", "true", "yes", "on"},
        max_research_rounds=int(os.getenv("VG_MAX_RESEARCH_ROUNDS", "1")),
        questions_per_round=int(os.getenv("VG_QUESTIONS_PER_ROUND", "5")),
        incidents_research_enabled=os.getenv("VG_INCIDENTS_RESEARCH_ENABLED", "").lower() in {"1", "true", "yes", "on"},
        disable_web_search=os.getenv("VG_DISABLE_WEB_SEARCH", "").lower() in {"1", "true", "yes", "on"},
    )


config = get_config()
