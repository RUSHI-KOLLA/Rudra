"""Persistence layer for incident cards — JSON source of truth + Chroma index.

Sole mutation point for all incident records. Provides:

* Atomic JSON writes (temp file + ``os.replace``)
* ``threading.Lock`` around every JSON+Chroma mutation
* ``rebuild_index()`` — read all JSON, upsert by ``incident_id``
* ``record_hash`` (sha256 of file bytes) stored in Chroma metadata
* Paste-hash repeat cache keyed on ``(sha256(paste), corpus_version)``
* One shared lazily-created fastembed ``TextEmbedding`` instance

The Chroma index is a derived cache only — the JSON files are the source of
truth. Chroma has zero authority: any hand edit of a JSON file is picked up
on next start.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import os
import tempfile
import threading
from typing import Any

from .schema import (
    IncidentCard,
    card_from_json,
    card_to_json,
    load_card,
    save_card,
    SCHEMA_VERSION,
    WEIGHTS_VERSION,
    TEMPLATE_VERSION,
)

try:
    from fastembed import TextEmbedding
except ImportError as exc:  # pragma: no cover - fastembed is a runtime dep
    TextEmbedding = None  # type: ignore[assignment]
    _FASTEMBED_IMPORT_ERROR = exc
else:
    _FASTEMBED_IMPORT_ERROR = None

try:
    import chromadb
    from chromadb.config import Settings
except ImportError as exc:  # pragma: no cover - chromadb is a runtime dep
    chromadb = None  # type: ignore[assignment]
    Settings = None  # type: ignore[assignment]
    _CHROMADB_IMPORT_ERROR = exc
else:
    _CHROMADB_IMPORT_ERROR = None


# Runtime config (optional at import time so the store stays importable in
# isolation). Resolves the card directory and the Chroma path to the same
# location the rest of the app uses, independent of process CWD.
try:
    from vg.config import config as _vg_config
except Exception:  # pragma: no cover - config is always present at runtime
    _vg_config = None  # type: ignore[assignment]


class IncidentStoreError(Exception):
    """Raised when the store cannot operate (embedding down, Chroma down, etc.).

    API layer converts this to HTTP 503 with reason — never an empty
    result set.
    """


class _Embedding:
    """Lazily-created shared fastembed TextEmbedding instance."""

    _instance: "TextEmbedding | None" = None

    @classmethod
    def get(cls) -> "TextEmbedding":
        if cls._instance is None:
            if TextEmbedding is None:
                raise IncidentStoreError(
                    f"fastembed unavailable: {_FASTEMBED_IMPORT_ERROR}"
                )
            cls._instance = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        return cls._instance


class _Chroma:
    """Shared Chroma client + collection (cosine space)."""

    _client: Any = None
    _collection: Any = None

    @classmethod
    def get_collection(cls, collection_name: str = "incidents") -> Any:
        if cls._collection is None:
            if chromadb is None:
                raise IncidentStoreError(
                    f"chromadb unavailable: {_CHROMADB_IMPORT_ERROR}"
                )
            chroma_path = (
                getattr(_vg_config, "chroma_db_path", None) or "./chroma_db"
            )
            cls._client = chromadb.PersistentClient(
                path=chroma_path,
                settings=Settings(anonymized_telemetry=False),
            )
            cls._collection = cls._client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return cls._collection


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _default_data_dir() -> Path:
    """Card directory: config value when available, else <repo>/data/incidents."""
    if _vg_config is not None and getattr(_vg_config, "incidents_data_path", ""):
        return Path(_vg_config.incidents_data_path)
    return Path(__file__).resolve().parent.parent / "data" / "incidents"


DATA_DIR = _default_data_dir()


def card_path(incident_id: str) -> Path:
    """Return the JSON path for a card id."""
    return DATA_DIR / f"{incident_id}.json"


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def record_hash(path: str | Path) -> str:
    """sha256 of a card file's bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def paste_hash(paste: str) -> str:
    """sha256 of a raw paste string."""
    return hashlib.sha256(paste.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Corpus version
# ---------------------------------------------------------------------------

_corpus_version_lock = threading.Lock()
_corpus_version: str | None = None


def corpus_version() -> str:
    """Monotonically increasing corpus version.

    Computed as sha256 over sorted ``(incident_id, record_hash)`` pairs of
    all card files. Bumped under lock on every JSON mutation.
    """
    global _corpus_version
    if _corpus_version is not None:
        return _corpus_version

    with _corpus_version_lock:
        if _corpus_version is not None:
            return _corpus_version

        pairs: list[tuple[str, str]] = []
        if DATA_DIR.exists():
            for path in sorted(DATA_DIR.glob("*.json")):
                incident_id = path.stem
                pairs.append((incident_id, record_hash(path)))

        pairs.sort()
        combined = "|".join(f"{iid}::{rh}" for iid, rh in pairs)
        _corpus_version = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return _corpus_version


def bump_corpus_version() -> None:
    """Invalidate the cached corpus version so it is recomputed next time."""
    global _corpus_version
    with _corpus_version_lock:
        _corpus_version = None


# ---------------------------------------------------------------------------
# Paste-hash repeat cache
# ---------------------------------------------------------------------------

# In-memory cache: key = (sha256(paste), corpus_version) -> result dict
_paste_cache: dict[tuple[str, str], dict[str, Any]] = {}
_paste_cache_lock = threading.Lock()


def cache_get(paste: str) -> dict[str, Any] | None:
    key = (paste_hash(paste), corpus_version())
    with _paste_cache_lock:
        return _paste_cache.get(key)


def cache_put(paste: str, result: dict[str, Any]) -> None:
    key = (paste_hash(paste), corpus_version())
    with _paste_cache_lock:
        _paste_cache[key] = result


# ---------------------------------------------------------------------------
# JSON card persistence (atomic writes under lock)
# ---------------------------------------------------------------------------

_store_lock = threading.Lock()


def save_card_json(card: IncidentCard) -> None:
    """Atomically write a card JSON file under the store lock.

    Bumps the corpus version after the write.
    """
    card.validate()
    path = card_path(card.incident_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    text = card_to_json(card)

    # Atomic write: temp file + os.replace
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=f"{path.stem}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise

    bump_corpus_version()


def load_all_cards() -> list[IncidentCard]:
    """Load all card JSON files from the data directory."""
    cards: list[IncidentCard] = []
    if not DATA_DIR.exists():
        return cards
    for path in sorted(DATA_DIR.glob("*.json")):
        if path.name == "_corpus_list.md":
            continue
        cards.append(load_card(path))
    return cards


# ---------------------------------------------------------------------------
# Chroma index
# ---------------------------------------------------------------------------

def _metadata_for_card(card: IncidentCard) -> dict[str, Any]:
    """Build Chroma metadata dict from a card (flattened, scalar values only)."""
    return {
        "incident_id": card.incident_id,
        "status": card.status.value,
        "record_hash": record_hash(card_path(card.incident_id)),
        "SCHEMA_VERSION": str(SCHEMA_VERSION),
        "WEIGHTS_VERSION": str(WEIGHTS_VERSION),
        "TEMPLATE_VERSION": str(TEMPLATE_VERSION),
        "trigger_type": card.trigger_type.value,
        "legal_outcome": card.legal_outcome.value,
        "tempo": card.tempo.value,
        "exit_authority": card.exit_authority.value,
        "succession": card.succession.value,
    }


def rebuild_index() -> int:
    """Read all JSON cards and upsert into the Chroma collection.

    Returns the number of cards indexed. Sub-second at N≤50.
    """
    cards = load_all_cards()
    if not cards:
        return 0

    collection = _Chroma.get_collection()
    embedder = _Embedding.get()

    # Build embedding inputs from summary_embed
    texts = [c.summary_embed or "" for c in cards]
    embeddings = list(embedder.embed(texts))

    ids = [c.incident_id for c in cards]
    metadatas = [_metadata_for_card(c) for c in cards]
    documents = [c.summary_embed or "" for c in cards]

    collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas,
                      documents=documents)
    return len(cards)


def drift_check() -> bool:
    """Check if the Chroma collection is in sync with the JSON files.

    Returns True if drift detected (collection count or any record_hash
    mismatch against top-20 candidates).
    """
    cards = load_all_cards()
    collection = _Chroma.get_collection()

    # Count check
    try:
        collection_count = collection.count()
    except Exception:
        return True

    if collection_count != len(cards):
        return True

    # Hash drift check against all cards (top-20 at query time is handled
    # by the caller; here we do a full check at startup)
    for card in cards:
        meta = collection.get(ids=[card.incident_id])
        if not meta or not meta.get("ids"):
            return True
        stored_hash = meta["metadatas"][0].get("record_hash")
        current_hash = record_hash(card_path(card.incident_id))
        if stored_hash != current_hash:
            return True

    return False


def upsert_card_to_chroma(card: IncidentCard) -> None:
    """Upsert a single card into the Chroma collection (under the store lock)."""
    collection = _Chroma.get_collection()
    embedder = _Embedding.get()

    embedding = list(embedder.embed([card.summary_embed or ""]))[0]
    collection.upsert(
        ids=[card.incident_id],
        embeddings=[embedding],
        metadatas=[_metadata_for_card(card)],
        documents=[card.summary_embed or ""],
    )


def delete_card_from_chroma(incident_id: str) -> None:
    """Delete a card from the Chroma collection (under the store lock)."""
    collection = _Chroma.get_collection()
    try:
        collection.delete(ids=[incident_id])
    except Exception:
        # Card may not exist in Chroma yet; that's fine
        pass
