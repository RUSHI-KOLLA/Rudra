"""Incident matching orchestration — Phase 3.

Pipeline for ``POST /api/incident-match``:

    paste -> extract (one small LLM call, one parse-repair retry, 0 on cache hit)
          -> structural gate (trigger_type + >= 2 actors)
          -> review state (panel edits the extracted fields)
          -> confirm -> build card
          -> ensure index -> embed query -> cosine top-20 pre-filter
          -> typed-field scoring (scoring.py) -> tiers
          -> mechanical why / where-breaks -> base rate -> silence line
          -> response with retrieval_debug, as_of and loop_audit

Deliberate properties, all from the design doc:

* No agents, no narrative LLM call, no web search anywhere in this module.
  The gap loop is Phase 4 and contributes ``loop_audit: []`` here.
* Cosine is a *filter only*. bge-small saturates at ~0.95 cosine on
  same-domain incident text, so it cannot discriminate structural shape; it
  prunes candidates and the eight typed-field terms do the ranking.
* Token ceiling: ``EXTRACTION_MAX_TOKENS`` x (1 call + at most 1 repair
  retry) + prompt stays under the 3.5k G4 ceiling. There is no second retry.
* Embedder/Chroma failures raise :class:`IncidentStoreError`, which the API
  layer turns into HTTP 503. Never an empty result set.
"""

from __future__ import annotations

import datetime as _dt
import json
from collections import Counter
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Optional

from .schema import (
    ACTOR_ROLES,
    SCHEMA_VERSION,
    ConstraintType,
    EscalationVector,
    ExitAuthority,
    IncidentCard,
    LegalOutcome,
    Outcome,
    Resolution,
    Status,
    Succession,
    SUMMARY_EMBED_FIELDS,
    Tempo,
    TimelineEntry,
    TriggerType,
    Tag,
    card_from_json,
    card_to_json,
    load_card,
)
from .scoring import (
    score,
    why_matches,
    where_breaks,
    tier_label,
    WEIGHTS_VERSION,
)
from .store import (
    IncidentStoreError,
    DATA_DIR,
    cache_get,
    cache_put,
    corpus_version,
    drift_check,
    load_all_cards,
    paste_hash,
    rebuild_index,
    save_card_json,
    upsert_card_to_chroma,
)
from .research import run_gap_loop
from .gaps import generate_questions

try:  # pragma: no cover - config is always present at runtime
    from vg.config import config as _vg_config
except Exception:  # pragma: no cover
    _vg_config = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Panel paste box limit. Longer pastes are truncated and flagged so the UI
#: can show the truncation notice.
MAX_PASTE_CHARS = 4000

#: Cosine pre-filter width. Top 20 by cosine are re-scored on typed fields.
COSINE_PRE_FILTER = 20

#: Matches returned to the panel (strong + weak inside the top-K).
TOP_K = 5

#: G4: 3.5k LLM tokens per fresh paste. Per-call cap of 1000 completion
#: tokens + a ~600 token prompt, times at most two calls, stays under it.
TOKEN_CEILING = 3500
EXTRACTION_MAX_TOKENS = 1000
EXTRACTION_TIMEOUT_SECONDS = 55

#: Structural gate: a paste is only usable if extraction filled these.
GATE_FIELDS = ("trigger_type",)
GATE_ACTOR_COUNT = 2

#: Fields that must be present before the match can run. List fields may be
#: empty (Jaccard of the empty set is 0 by definition) but the scalar typed
#: fields and actor_roles must be set, or the score would be meaningless.
CONFIRM_SCALAR_FIELDS = (
    "title",
    "date",
    "trigger_type",
    "tempo",
    "exit_authority",
    "succession",
    "sector",
    "actor_roles",
)
CONFIRM_LIST_FIELDS = ("constraint_types", "escalation_vector", "resolution")

#: Silence line feeds: the nine canonical embed fields plus the two that are
#: reported but never scored.
SILENCE_FIELDS = tuple(SUMMARY_EMBED_FIELDS) + ("geography", "legal_outcome")

#: Enum values that mean "the record does not establish this".
_ABSENT_ENUM_VALUES = frozenset({"none", "unknown"})

#: Sentinel used when a paste has no usable title line.
_UNTITLED = "Pasted incident"


class ExtractionIncomplete(Exception):
    """Extraction could not fill the required fields.

    The API layer turns this into HTTP 422 ``needs_manual_entry`` with the
    raw paste spooled to ``data/incidents/_raw/`` and no card written.
    """

    def __init__(self, missing: list[str], raw_paste: str, spooled_path: str = ""):
        self.missing = missing
        self.raw_paste = raw_paste
        self.spooled_path = spooled_path
        super().__init__(f"missing required fields: {', '.join(missing)}")


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


def _system_prompt() -> str:
    """Fixed extraction prompt, built from the schema's closed vocabularies."""
    return (
        "You extract a typed incident record from a news paste.\n"
        "Return ONLY one JSON object. No prose, no markdown, no code fence.\n"
        "Keys and allowed values:\n"
        f"  title: string\n"
        f"  date: YYYY-MM-DD\n"
        f"  trigger: one sentence free text\n"
        f"  trigger_type: one of {_enum_values(TriggerType)}\n"
        f"  actors: array of person or organisation names (at least 2)\n"
        f"  actor_roles: array from {list(ACTOR_ROLES)} (roles of the actors)\n"
        f"  constraint_types: array from {_enum_values(ConstraintType)}\n"
        f"  escalation_vector: array from {_enum_values(EscalationVector)}\n"
        f"  tempo: one of {_enum_values(Tempo)}\n"
        f"  exit_authority: one of {_enum_values(ExitAuthority)}\n"
        f"  succession: one of {_enum_values(Succession)}\n"
        f"  resolution: array from {_enum_values(Resolution)}\n"
        f"  legal_outcome: one of {_enum_values(LegalOutcome)}\n"
        "  sector: string\n"
        "  geography: string\n"
        "  timeline: array of {date: YYYY-MM-DD, event: string}\n"
        "Use an empty array when the paste does not establish a value.\n"
        "Never invent facts. Never add keys."
    )


def _parse_json(raw: str) -> tuple[Optional[dict[str, Any]], str]:
    """Parse the model reply, tolerating a ```json fence."""
    text = (raw or "").strip()
    if not text:
        return None, "empty response"
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, str(exc)
    if not isinstance(parsed, dict):
        return None, "response was a JSON value but not an object"
    return parsed, ""


async def _default_extractor(
    system: str,
    user: str,
    *,
    api_key: Optional[str] = None,
) -> str:
    """The one small-model call. Injected in tests."""
    from vg.core.llm_client import get_async_llm_client

    client = get_async_llm_client(provider="groq", api_key=api_key)
    # max_retries=1: no transport retries. The only retry in incident mode is
    # the parse-repair below, so the G4 token ceiling stays deterministic.
    return await client.chat(
        system,
        user,
        temperature=0.0,
        max_tokens=EXTRACTION_MAX_TOKENS,
        timeout_seconds=EXTRACTION_TIMEOUT_SECONDS,
        max_retries=1,
    )


def spool_raw_paste(paste: str) -> str:
    """Persist the raw paste under ``data/incidents/_raw/`` (idempotent)."""
    raw_dir = DATA_DIR / "_raw"
    try:
        raw_dir.mkdir(parents=True, exist_ok=True)
        path = raw_dir / f"{paste_hash(paste)[:16]}.txt"
        if not path.exists():
            path.write_text(paste, encoding="utf-8")
        return str(path)
    except OSError:
        # Spooling is best effort; the paste still rides along in the
        # needs_manual_entry response either way.
        return ""


async def _extract_json(
    system: str,
    user: str,
    paste: str,
    *,
    api_key: Optional[str],
    extractor: Optional[Callable[..., Awaitable[str]]],
    missing_label: str,
) -> dict[str, Any]:
    """One model call + at most one parse-repair retry (G4: no second retry).

    Transport/auth failures propagate as :class:`ExtractionIncomplete` with
    ``missing=[missing_label]`` so the API layer returns the same
    ``needs_manual_entry`` contract as a structurally incomplete extraction —
    an outage must not look like a bare 500 (ruling R4).
    """
    fn = extractor or _default_extractor
    try:
        raw = await fn(system, user, api_key=api_key)
    except ExtractionIncomplete:
        raise
    except Exception as exc:
        raise ExtractionIncomplete(
            [missing_label],
            paste,
            spool_raw_paste(paste),
        ) from exc

    parsed, err = _parse_json(raw)
    if parsed is None:
        try:
            raw = await fn(
                system,
                f"{user}\n\nYour previous reply was not valid JSON ({err}). "
                "Reply with the JSON object only.",
                api_key=api_key,
            )
        except Exception as exc:
            raise ExtractionIncomplete(
                [missing_label], paste, spool_raw_paste(paste)
            ) from exc
        parsed, err = _parse_json(raw)

    if parsed is None:
        raise ExtractionIncomplete([missing_label], paste, spool_raw_paste(paste))
    return parsed


async def extract_card(
    paste: str,
    *,
    api_key: Optional[str] = None,
    extractor: Optional[Callable[..., Awaitable[str]]] = None,
) -> dict[str, Any]:
    """Extract a candidate card dict from the paste.

    One call, then at most one repair retry that re-sends the *same* prompt
    with the parse error appended. No second retry.
    """
    return await _extract_json(
        _system_prompt(),
        f"Paste:\n{paste}",
        paste,
        api_key=api_key,
        extractor=extractor,
        missing_label="extraction",
    )


# ---------------------------------------------------------------------------
# Structural gate
# ---------------------------------------------------------------------------

def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple)):
        return len(value) == 0
    return False


def review_missing(extracted: dict[str, Any]) -> list[str]:
    """Fields the panel cannot render a structured review without.

    Exactly the design's precondition: ``trigger_type`` plus at least two
    named actors. Anything else is editable in the review state.
    """
    missing: list[str] = []
    trigger_type = str(extracted.get("trigger_type") or "").strip()
    if trigger_type not in set(_enum_values(TriggerType)):
        missing.append("trigger_type")

    actors = [
        str(a).strip()
        for a in (extracted.get("actors") or [])
        if str(a).strip()
    ]
    if len(actors) < GATE_ACTOR_COUNT:
        missing.append("actors")
    return missing


#: Scalar fields whose value must be a member of a closed vocabulary.
_CONFIRM_ENUM_FIELDS: dict[str, type[Enum]] = {
    "trigger_type": TriggerType,
    "tempo": Tempo,
    "exit_authority": ExitAuthority,
    "succession": Succession,
}


def confirm_missing(extracted: dict[str, Any]) -> list[str]:
    """Everything that must be set before scoring, or the score is noise."""
    missing: list[str] = []
    for name in CONFIRM_SCALAR_FIELDS:
        if _blank(extracted.get(name)):
            missing.append(name)
            continue
        enum_cls = _CONFIRM_ENUM_FIELDS.get(name)
        if enum_cls is not None and str(extracted[name]) not in set(
            _enum_values(enum_cls)
        ):
            missing.append(name)
    for name in CONFIRM_LIST_FIELDS:
        if extracted.get(name) is None:
            missing.append(name)
    # actor_roles must be from the closed vocabulary of 12 roles
    roles = [str(r) for r in (extracted.get("actor_roles") or [])]
    if roles and not all(r in ACTOR_ROLES for r in roles):
        missing.append("actor_roles")
    missing.extend(review_missing(extracted))
    # de-duplicate, preserve order
    seen: set[str] = set()
    ordered = [m for m in missing if not (m in seen or seen.add(m))]
    return ordered


def structural_mode_gate(question: str) -> bool:
    """Zero-token gate: does this input belong to incident mode?

    True when the input reads like a pasted incident (a dated event with an
    actor) rather than a forecast question. The debate path never runs when
    this returns True, and no coordinator is constructed either way.
    """
    text = (question or "").strip()
    if not text:
        return True
    lowered = text.lower()
    forecast_cues = (
        "will ", "would ", "could ", "shall ", "might ",
        "predict", "forecast", "probability", "likely to",
    )
    return not any(cue in lowered for cue in forecast_cues)


# ---------------------------------------------------------------------------
# Card construction
# ---------------------------------------------------------------------------

def build_card(
    extracted: dict[str, Any],
    *,
    paste: str,
) -> IncidentCard:
    """Turn reviewed fields into an IncidentCard (never written to disk)."""
    missing = confirm_missing(extracted)
    if missing:
        raise ExtractionIncomplete(missing, paste, spool_raw_paste(paste))

    def _list(name: str, enum_cls: type[Enum]) -> list[Any]:
        out, seen = [], set()
        for raw in extracted.get(name) or []:
            try:
                member = enum_cls(raw)
            except (ValueError, KeyError):
                continue
            if member.value not in seen:
                seen.add(member.value)
                out.append(member)
        return out

    def _scalar(name: str, enum_cls: type[Enum], default: Any = None) -> Any:
        try:
            return enum_cls(str(extracted.get(name)))
        except ValueError:
            # Ungated field (legal_outcome) supplied an out-of-vocabulary
            # value: fall back to the neutral member rather than 500.
            if default is not None:
                return default
            raise

    incident_id = f"paste_{paste_hash(paste)[:12]}"
    timeline_raw = extracted.get("timeline") or []
    timeline = []
    for entry in timeline_raw[:40]:
        if not isinstance(entry, dict):
            continue
        timeline.append(
            TimelineEntry(
                date=str(entry.get("date") or extracted.get("date") or ""),
                event=str(entry.get("event") or "").strip(),
                claim_ids=[],
            )
        )

    # Closed vocabulary: keep only the 12 legal roles (extraction may
    # paraphrase); an all-invalid list still fails confirm_missing upstream.
    known_roles = [
        str(r) for r in (extracted.get("actor_roles") or []) if str(r) in ACTOR_ROLES
    ]

    card = IncidentCard(
        incident_id=incident_id,
        title=str(extracted.get("title") or _UNTITLED).strip() or _UNTITLED,
        status=Status.PROVISIONAL,
        date=str(extracted.get("date") or "").strip(),
        recorded_at=_dt.date.today().isoformat(),
        actors=[str(a).strip() for a in (extracted.get("actors") or []) if str(a).strip()],
        actor_roles=known_roles,
        sector=str(extracted.get("sector") or "").strip(),
        geography=str(extracted.get("geography") or "").strip(),
        trigger=str(extracted.get("trigger") or "").strip(),
        trigger_type=_scalar("trigger_type", TriggerType),
        constraint_types=_list("constraint_types", ConstraintType),
        legal_outcome=_scalar("legal_outcome", LegalOutcome, default=LegalOutcome.NONE),
        escalation_vector=_list("escalation_vector", EscalationVector),
        tempo=_scalar("tempo", Tempo),
        exit_authority=_scalar("exit_authority", ExitAuthority),
        succession=_scalar("succession", Succession),
        timeline=timeline,
        resolution=_list("resolution", Resolution),
        outcome=None,
        claims=[],
        sources=[],
        summary_embed="",           # built by __post_init__ from canonical fields
    )
    return card


# ---------------------------------------------------------------------------
# Silence line
# ---------------------------------------------------------------------------

def _field_is_empty(card: IncidentCard, name: str) -> bool:
    value = getattr(card, name, None)
    if value is None:
        return True
    if isinstance(value, Enum):
        return value.value in _ABSENT_ENUM_VALUES
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple)):
        return len(value) == 0
    return False


def _downgraded_claims(card: IncidentCard) -> list[Any]:
    """Claims with the load-time provenance downgrade applied.

    ``card_from_json`` is the single implementation of the downgrade
    (documented -> reported_unconfirmed when the excerpt file is absent),
    so the silence line counts the tags the panel will actually render.
    """
    if not card.claims:
        return []
    try:
        return card_from_json(card_to_json(card)).claims
    except Exception:  # pragma: no cover - defensive, never block a response
        return list(card.claims)


def build_silence_line(
    card: IncidentCard,
    loop_audit: Iterable[dict[str, Any]],
    as_of: str,
) -> str:
    """One dated line naming what the record does not establish.

    Three feeds, at most three clauses, zero-count clauses dropped.
    """
    clauses: list[str] = []

    empty_fields = [name for name in SILENCE_FIELDS if _field_is_empty(card, name)]
    if empty_fields:
        clauses.append(
            f"{len(empty_fields)} of {len(SILENCE_FIELDS)} structural fields "
            f"empty on the pasted record ({', '.join(empty_fields)})"
        )

    below = [
        claim.tag.value
        for claim in _downgraded_claims(card)
        if claim.tag != Tag.DOCUMENTED
    ]
    if below:
        distinct = ", ".join(sorted(set(below)))
        clauses.append(
            f"{len(below)} claim(s) below documented ({distinct})"
        )

    no_source = [
        entry for entry in loop_audit
        if entry.get("source") in (None, "")
    ]
    if no_source:
        clauses.append(
            f"{len(no_source)} research question(s) closed with no source available"
        )

    if not clauses:
        return f"As of {as_of}: nothing in this record is unestablished."
    return f"As of {as_of}: " + "; ".join(clauses) + "."


# ---------------------------------------------------------------------------
# Base rate
# ---------------------------------------------------------------------------

def _outcome_bucket(card: IncidentCard) -> str:
    if card.resolution:
        return card.resolution[0].value
    return card.succession.value


def compute_base_rate(
    *,
    strong_cards: list[IncidentCard],
    query_card: IncidentCard,
    curated: list[IncidentCard],
) -> dict[str, Any]:
    """Corpus frequency of the structural signature, with explicit counts.

    Numerator = the strong tier when it is non-empty, else every curated
    card sharing the paste's trigger_type. Denominator = the curated corpus.
    Weak-tier cards and provisional cards are never counted.
    """
    corpus_size = len(curated)
    query_trigger = query_card.trigger_type.value

    if strong_cards:
        counted = list(strong_cards)
        label = "share this shape"
        scope = "shape"
    else:
        counted = [
            c for c in curated if c.trigger_type.value == query_trigger
        ]
        label = "share this trigger type"
        scope = "trigger_type"

    count = len(counted)
    distribution = dict(Counter(_outcome_bucket(c) for c in counted))

    dist_text = ", ".join(
        f"{n} {key}" for key, n in sorted(distribution.items(), key=lambda kv: (-kv[1], kv[0]))
    )

    if scope == "shape":
        if count == 0:
            text = f"No recorded case matches this shape (0 of {corpus_size})."
        else:
            text = f"{count} of {corpus_size} recorded cases {label}"
            if dist_text:
                text += f"; {dist_text}"
            text += "."
            if count < 2:
                text += " Thin sample: 1 of the corpus, indicative only."
    else:
        if count == 0:
            text = (
                f"No recorded case shares trigger type {query_trigger} "
                f"(0 of {corpus_size})."
            )
        else:
            text = (
                f"{count} of {corpus_size} recorded cases {label} "
                f"{query_trigger}"
            )
            if dist_text:
                text += f"; {dist_text}"
            text += "."
            if count < 2:
                text += " Thin sample: treat as indicative only."

    return {
        "count": count,
        "denominator": corpus_size,
        "corpus_size": corpus_size,
        "trigger_type": query_trigger,
        "scope": scope,
        "distribution": distribution,
        "text": text,
    }


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _curated_and_provisional() -> tuple[list[IncidentCard], int]:
    cards = load_all_cards()
    curated = [c for c in cards if c.status == Status.CURATED]
    return curated, len(cards) - len(curated)


def _ensure_index(expected: int) -> None:
    """Rebuild the Chroma index when it has drifted from the JSON corpus."""
    if expected == 0:
        return
    try:
        in_sync = not drift_check()
    except IncidentStoreError:
        raise
    except Exception as exc:  # pragma: no cover - chroma failure path
        raise IncidentStoreError(f"incident index unavailable: {exc}") from exc
    if not in_sync:
        rebuild_index()


def _get_embedder(embedder: Any = None) -> Any:
    if embedder is not None:
        return embedder
    from .store import _Embedding
    return _Embedding.get()


def _get_collection(collection: Any = None) -> Any:
    if collection is not None:
        return collection
    from .store import _Chroma
    return _Chroma.get_collection(
        getattr(_vg_config, "incidents_collection", None) or "incidents"
    )


def _retrieve_candidates(
    query_card: IncidentCard,
    curated: list[IncidentCard],
    provisional_count: int,
    *,
    embedder: Any = None,
    collection: Any = None,
) -> list[dict[str, Any]]:
    """Cosine pre-filter: top-COSINE_PRE_FILTER by 1 - distance, curated only."""
    emb = _get_embedder(embedder)
    col = _get_collection(collection)

    try:
        query_vector = list(emb.embed([query_card.summary_embed]))[0]
        count = col.count()
        if count == 0:
            return []
        n_results = min(count, COSINE_PRE_FILTER + provisional_count)
        result = col.query(
            query_embeddings=[query_vector],
            n_results=n_results,
            include=["metadatas", "distances"],
        )
    except IncidentStoreError:
        raise
    except Exception as exc:
        raise IncidentStoreError(f"embedder or index unavailable: {exc}") from exc

    ids = (result.get("ids") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]

    by_id = {c.incident_id: c for c in curated}
    rows: list[dict[str, Any]] = []
    for incident_id, distance, metadata in zip(ids, distances, metadatas):
        card = by_id.get(incident_id)
        if card is None:
            # Provisional or unknown record: excluded by LOCKED 5.
            continue
        # Chroma cosine space returns distance = 1 - similarity.
        cosine = 1.0 - float(distance)
        rows.append({"card": card, "cosine": cosine, "metadata": metadata})

    rows.sort(key=lambda r: r["cosine"], reverse=True)
    return rows[:COSINE_PRE_FILTER]


async def run_match(
    *,
    paste: str,
    api_key: Optional[str] = None,
    extracted: Optional[dict[str, Any]] = None,
    extractor: Optional[Callable[..., Awaitable[str]]] = None,
    embedder: Any = None,
    collection: Any = None,
) -> dict[str, Any]:
    """Full incident match. Raises ExtractionIncomplete / IncidentStoreError.

    Two-phase contract (request body ``{paste, extracted?}``):

    * ``extracted`` absent — Phase 1. Repeat-cache check (0 LLM tokens on a
      hit), otherwise one extraction call; the structural gate runs on the
      result and the response is ``{"status": "reviewing", extracted_card}``
      for the panel's review/edit state. A failed gate raises
      :class:`ExtractionIncomplete` → HTTP 422 ``needs_manual_entry`` with
      the paste spooled.
    * ``extracted`` present — Phase 2 (user confirmed the fields). 0 LLM
      tokens: build the card, ensure the index, embed, cosine top-20, score,
      tier, explain, base rate, silence line, cache the result.

    Deliberately agent-free: no coordinator, no search, no narrative call.
    """
    truncated = len(paste) > MAX_PASTE_CHARS
    if truncated:
        paste = paste[:MAX_PASTE_CHARS]

    if not paste.strip():
        raise ExtractionIncomplete(["paste"], paste, "")

    # Repeat cache: same paste + same corpus version → replay, 0 tokens.
    cached = cache_get(paste)
    if cached is not None:
        return {**cached, "cache_hit": True, "truncated": truncated}

    # ---- Phase 1: extract + gate --------------------------------------
    if extracted is None:
        data = await extract_card(paste, api_key=api_key, extractor=extractor)
        missing = review_missing(data)
        if missing:
            raise ExtractionIncomplete(missing, paste, spool_raw_paste(paste))
        return {
            "status": "reviewing",
            "extracted_card": data,
            "paste_chars": len(paste),
            "truncated": truncated,
            "as_of": _dt.date.today().isoformat(),
        }

    # ---- Phase 2: user-confirmed fields, zero LLM tokens ---------------
    missing = confirm_missing(extracted)
    if missing:
        raise ExtractionIncomplete(missing, paste, spool_raw_paste(paste))

    card = build_card(extracted, paste=paste)
    curated, provisional_count = _curated_and_provisional()

    as_of = _dt.date.today().isoformat()

    # Empty corpus: distinguishable from "no match".
    if not curated:
        return {
            "status": "complete",
            "matches": [],
            "corpus_size": 0,
            "base_rate": compute_base_rate(
                strong_cards=[], query_card=card, curated=[]
            ),
            "silence_line": build_silence_line(card, [], as_of),
            "as_of": as_of,
            "loop_audit": [],
            "retrieval_debug": _retrieval_debug(
                card, cosine_rows=[], scored=0, llm_calls=0, corpus_size=0,
                provisional_count=provisional_count, cache="miss",
            ),
            "truncated": truncated,
        }

    _ensure_index(len(curated))

    rows = _retrieve_candidates(
        card, curated, provisional_count, embedder=embedder, collection=collection
    )

    scored: list[dict[str, Any]] = []
    for row in rows:
        result = score(card, row["card"])
        scored.append(
            {
                "id": row["card"].incident_id,
                "score": round(result["score"], 4),
                "components": result["components"],
                "cosine": round(row["cosine"], 4),
                "tier": tier_label(
                    result["score"],
                    getattr(_vg_config, "incident_weak_threshold", 0.3222)
                    if _vg_config is not None
                    else 0.3222,
                ),
                "why": why_matches(result),
                "breaks": where_breaks(result),
                "card": row["card"].to_dict(),
            }
        )
    scored.sort(key=lambda m: m["score"], reverse=True)
    matches = scored[:TOP_K]

    strong_cards = [
        row["card"]
        for row in rows
        if row["card"].incident_id in _strong_ids(matches)
    ]

    base_rate = compute_base_rate(
        strong_cards=strong_cards, query_card=card, curated=curated
    )

    # Phase 4: Research loop (behind feature flag)
    loop_audit = []
    if getattr(_vg_config, "incidents_research_enabled", False):
        from .gaps import generate_questions
        from .research import run_gap_loop

        questions = generate_questions(card)
        if questions:
            loop_audit = await run_gap_loop(questions, max_rounds=getattr(_vg_config, "max_research_rounds", 2))
        else:
            loop_audit = []
    else:
        loop_audit = []

    result = {
        "status": "complete",
        "matches": matches,
        "corpus_size": len(curated),
        "base_rate": base_rate,
        "silence_line": build_silence_line(card, loop_audit, as_of),
        "as_of": as_of,
        "loop_audit": loop_audit,
        "retrieval_debug": _retrieval_debug(
            card,
            cosine_rows=rows,
            scored=len(scored),
            llm_calls=0,
            corpus_size=len(curated),
            provisional_count=provisional_count,
            cache="miss",
        ),
        "weights_version": WEIGHTS_VERSION,
        "truncated": truncated,
    }
    cache_put(paste, result)
    return result


def _strong_ids(matches: list[dict[str, Any]]) -> set[str]:
    return {m["id"] for m in matches if m.get("tier") == "strong"}


def _retrieval_debug(
    card: IncidentCard,
    *,
    cosine_rows: list[dict[str, Any]],
    scored: int,
    llm_calls: int,
    corpus_size: int,
    provisional_count: int,
    cache: str,
) -> dict[str, Any]:
    """Everything the panel needs to show how the list was produced."""
    return {
        "schema_version": SCHEMA_VERSION,
        "weights_version": WEIGHTS_VERSION,
        "weak_threshold": (
            getattr(_vg_config, "incident_weak_threshold", 0.3222)
            if _vg_config is not None
            else 0.3222
        ),
        "cosine_prefilter": COSINE_PRE_FILTER,
        "top_k": TOP_K,
        "candidates_by_cosine": len(cosine_rows),
        "candidates_scored": scored,
        "corpus_size": corpus_size,
        "provisional_excluded": provisional_count,
        "collection": (
            getattr(_vg_config, "incidents_collection", None) or "incidents"
        ),
        "query_card": card.incident_id,
        "corpus_version": corpus_version(),
        "llm_calls": llm_calls,
        "cache": cache,
        "cosine_top": [
            {"id": r["card"].incident_id, "cosine": round(r["cosine"], 4)}
            for r in cosine_rows[:TOP_K]
        ],
    }


# ---------------------------------------------------------------------------
# Outcome recording (POST /api/incident-outcome)
# ---------------------------------------------------------------------------

_OUTCOME_SYSTEM = (
    "You map a free-text incident outcome onto typed fields.\n"
    "Return ONLY one JSON object with keys:\n"
    "  summary: one sentence\n"
    "  resolution: array from "
    f"{[member.value for member in Resolution]}\n"
    "  succession: one of "
    f"{[member.value for member in Succession]}\n"
    "Use empty array / the neutral value when the text does not establish it.\n"
    "Never invent facts. Never add keys."
)


async def record_outcome(
    *,
    incident_id: str,
    outcome_text: str,
    api_key: Optional[str] = None,
    extractor: Optional[Callable[..., Awaitable[str]]] = None,
    user_confirmed: bool = False,
    proposed_outcome: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Map free text onto an existing card's outcome (one small LLM call).

    Two-phase contract (per reviewer):
    - Phase 1: user_confirmed=False, proposed_outcome=None.
      Returns {"status": "reviewing", "proposed_outcome": {...}} with model-mapped fields.
    - Phase 2: user_confirmed=True, proposed_outcome={...} (user-confirmed fields).
      Writes card JSON only (NO Chroma upsert — no re-embed on outcome).
      Returns {"status": "recorded", "incident_id": incident_id}.

    Raises LookupError (unknown card), ExtractionIncomplete (mapping failed —
    API layer returns 422), IncidentStoreError (JSON write failed — 503).
    """
    path = DATA_DIR / f"{incident_id}.json"
    if not path.exists():
        raise LookupError(incident_id)

    # Phase 1: extract proposed outcome, return for user review
    if not user_confirmed:
        data = await _extract_json(
            _OUTCOME_SYSTEM,
            f"Recorded outcome text:\n{outcome_text}",
            outcome_text,
            api_key=api_key,
            extractor=extractor,
            missing_label="outcome",
        )

        proposed = {
            "summary": str(data.get("summary") or outcome_text).strip(),
            "resolution": _outcome_enums(data, "resolution", Resolution),
            "succession": str(data.get("succession") or "").strip(),
            "constraint_types": [],
        }

        return {
            "status": "reviewing",
            "proposed_outcome": proposed,
            "incident_id": incident_id,
        }

    # Phase 2: user confirmed the proposed outcome
    if proposed_outcome is None:
        raise ValueError("proposed_outcome required when user_confirmed=True")

    card = load_card(path)
    card.outcome = Outcome(
        summary=str(proposed_outcome.get("summary") or "").strip(),
        constraint_types=[],
        recorded_at=_dt.date.today().isoformat(),
        sources=[],
    )
    resolutions = proposed_outcome.get("resolution", [])
    if resolutions:
        card.resolution = resolutions
    succession = str(proposed_outcome.get("succession") or "").strip()
    if succession:
        try:
            card.succession = Succession(succession)
        except ValueError:
            pass

    save_card_json(card)  # atomic write + bump_corpus_version()
    # NO Chroma upsert on outcome — no re-embed. summary_embed doesn't include outcome fields.

    return {"status": "recorded", "incident_id": incident_id}


def _outcome_enums(data: dict[str, Any], key: str, enum_cls: type[Enum]) -> list[Any]:
    out, seen = [], set()
    for raw in data.get(key) or []:
        try:
            member = enum_cls(raw)
        except (ValueError, KeyError, TypeError):
            continue
        if member.value not in seen:
            seen.add(member.value)
            out.append(member)
    return out
