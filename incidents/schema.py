"""Incident record schema — zero-agent structural incident memory.

Defines the IncidentCard dataclass, strict enums and closed vocabularies,
the mechanical tag cascade, JSON round-trip and validation, and the fixed
``summary_embed`` template.

The model never writes ``summary_embed``; a template change forces a full
re-embed. Claim ids are ``c1``…``cn`` in list order, local to the card.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import json

# Schema / weights / template versioning. All three bump together on any
# change to the card schema, the scoring weights, or the summary_embed
# template. Store metadata records these versions; a mismatch triggers
# a full re-embed / reindex.
SCHEMA_VERSION = 7
WEIGHTS_VERSION = 7
TEMPLATE_VERSION = 7


# ---------------------------------------------------------------------------
# Closed vocabularies (enums)
# ---------------------------------------------------------------------------

class Status(str, Enum):
    CURATED = "curated"
    PROVISIONAL = "provisional"


class Tag(str, Enum):
    DOCUMENTED = "documented"
    REPORTED_UNCONFIRMED = "reported_unconfirmed"
    INFERRED = "inferred"
    SPECULATIVE = "speculative"


class TriggerType(str, Enum):
    PERSONAL_CONDUCT = "personal_conduct"
    MARKET_SHOCK = "market_shock"
    REGULATORY = "regulatory"
    INTERNAL_CONFLICT = "internal_conflict"
    EXTERNAL_ATTACK = "external_attack"
    POLICY_SHIFT = "policy_shift"
    FRAUD = "fraud"
    OPERATIONAL_FAILURE = "operational_failure"
    OFFICIAL_MISCONDUCT = "official_misconduct"


class ConstraintType(str, Enum):
    LEGAL = "legal"
    REGULATORY = "regulatory"
    MARKET = "market"
    REPUTATIONAL = "reputational"
    SECURITY = "security"


class LegalOutcome(str, Enum):
    NONE = "none"
    PENDING = "pending"
    CHARGES_DROPPED = "charges_dropped"
    CONVICTED = "convicted"
    ACQUITTED = "acquitted"
    SETTLED = "settled"
    PARDONED = "pardoned"
    FLED = "fled"


class EscalationVector(str, Enum):
    LEAK = "leak"
    FILING = "filing"
    INQUIRY = "inquiry"
    ULTIMATUM = "ultimatum"
    RESIGN_SIGNAL = "resign_signal"
    MEDIA_CYCLE = "media_cycle"


class Tempo(str, Enum):
    HOURS = "hours"
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"
    YEARS = "years"


class ExitAuthority(str, Enum):
    SELF = "self"
    BOARD = "board"
    INVESTORS = "investors"
    COURT = "court"
    REGULATOR = "regulator"
    ELECTORATE = "electorate"
    LEGISLATURE = "legislature"


class Succession(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    CONTESTED = "contested"
    UNKNOWN = "unknown"


class Resolution(str, Enum):
    RESIGNATION = "resignation"
    DISMISSAL = "dismissal"
    SETTLEMENT = "settlement"
    ONGOING = "ongoing"
    ACQUITTAL = "acquittal"
    CONVICTION = "conviction"
    BANKRUPTCY = "bankruptcy"
    DISSOLUTION = "dissolution"
    GROUNDING = "grounding"
    GOVERNMENT_APPOINTED_BOARD = "government_appointed_board"
    TECH_MAHINDRA_ACQUISITION = "tech_mahindra_acquisition"


def _enum_value(v: Any) -> str:
    """Return the string value of an enum, or the string itself."""
    return v.value if isinstance(v, Enum) else str(v)


# Closed flat vocabulary of twelve actor roles. NOT positionally aligned
# with actors. Adding a value is a schema version bump.
ACTOR_ROLES = (
    "ceo",
    "founder",
    "cfo",
    "board",
    "employee",
    "regulator",
    "court",
    "intelligence_agency",
    "government",
    "investor",
    "customer",
    "media",
    "president",
    "prime_minister",
    "minister",
    "party_official",
)

# Constraint type dominance precedence (highest first).
CONSTRAINT_PRECEDENCE = (
    ConstraintType.LEGAL,
    ConstraintType.REGULATORY,
    ConstraintType.MARKET,
    ConstraintType.REPUTATIONAL,
    ConstraintType.SECURITY,
)


# ---------------------------------------------------------------------------
# Tag precedence cascade (applied mechanically at ingest, in order)
# ---------------------------------------------------------------------------

# Cascade order (fixed): speculative -> documented -> reported_unconfirmed -> inferred.
# Forward-looking beats everything.
# ``documented`` requires the excerpt file present at load.
# ``inferred`` requires a non-empty ``supports`` list; without it, downgrade
# to ``reported_unconfirmed``.


def apply_tag_cascade(
    tag: Tag,
    is_forward_looking: bool,
    has_excerpt_file: bool,
    supports: list[str],
) -> Tag:
    """Apply the mechanical tag precedence cascade.

    Rules are evaluated in order. The first matching rule wins.
    """
    # Rule 1: Forward-looking or hypothetical -> speculative
    if is_forward_looking:
        return Tag.SPECULATIVE

    # Rule 2: Primary source directly cited AND document attached with
    # excerpt stored -> documented
    if tag == Tag.DOCUMENTED and has_excerpt_file:
        return Tag.DOCUMENTED

    # Rule 3: No primary document -> reported_unconfirmed
    # (covers attributed media reporting and bare assertions alike)
    if not has_excerpt_file:
        return Tag.REPORTED_UNCONFIRMED

    # Rule 4: Residual conclusions drawn from other claims -> inferred,
    # listing supporting claim ids in ``supports``.
    if tag == Tag.INFERRED and supports:
        return Tag.INFERRED

    # Fallback: anything that reaches here without a more specific tag
    # is reported_unconfirmed.
    return Tag.REPORTED_UNCONFIRMED


# ---------------------------------------------------------------------------
# summary_embed template (canonical fields only; model never writes it)
# ---------------------------------------------------------------------------

# Canonical field order for the embedding template. Free-text ``trigger`` and
# ``geography`` are excluded — both reward surface similarity over structure.
SUMMARY_EMBED_FIELDS = (
    "trigger_type",
    "actor_roles",
    "constraint_types",
    "escalation_vector",
    "resolution",
    "tempo",
    "exit_authority",
    "succession",
    "sector",
)


def summary_embed_template(card: dict[str, Any]) -> str:
    """Build the fixed embedding string from a card dict.

    Only canonical fields are included, in a deterministic order. List fields
    are sorted and joined with ``; ``. ``resolution`` uses only the first
    (primary) element.
    """
    parts: list[str] = []

    for field_name in SUMMARY_EMBED_FIELDS:
        value = card.get(field_name)
        if value is None:
            continue

        if field_name == "resolution":
            # Use only the primary (first) resolution element
            if isinstance(value, list) and value:
                parts.append(_enum_value(value[0]))
            elif isinstance(value, str):
                parts.append(value)
        elif isinstance(value, list):
            parts.append("; ".join(sorted(_enum_value(v) for v in value)))
        elif isinstance(value, str):
            parts.append(value)
        else:
            parts.append(str(value))

    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Card dataclass
# ---------------------------------------------------------------------------


@dataclass
class Source:
    id: str
    type: str
    ref: str
    date: str


@dataclass
class Claim:
    id: str
    text: str
    tag: Tag
    source_ids: list[str] = field(default_factory=list)
    supports: list[str] = field(default_factory=list)


@dataclass
class TimelineEntry:
    date: str
    event: str
    claim_ids: list[str] = field(default_factory=list)


@dataclass
class Outcome:
    summary: str
    actors: list[str] = field(default_factory=list)
    constraint_types: list[ConstraintType] = field(default_factory=list)
    recorded_at: Optional[str] = None
    sources: list[Source] = field(default_factory=list)


@dataclass
class IncidentCard:
    incident_id: str
    title: str
    status: Status
    date: str
    recorded_at: str
    actors: list[str]
    actor_roles: list[str]
    sector: str
    geography: str
    trigger: str
    trigger_type: TriggerType
    constraint_types: list[ConstraintType]
    legal_outcome: LegalOutcome
    escalation_vector: list[EscalationVector]
    tempo: Tempo
    exit_authority: ExitAuthority
    succession: Succession
    timeline: list[TimelineEntry]
    resolution: list[Resolution]
    outcome: Optional[Outcome] = None
    claims: list[Claim] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    summary_embed: str = ""
    external_pressure: str = ""
    unverified: bool = False

    def __post_init__(self) -> None:
        # Build summary_embed if empty (model never writes it directly)
        if not self.summary_embed:
            self.summary_embed = summary_embed_template(self.to_dict())

    # -- serialization helpers ---------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IncidentCard":
        # Reconstruct nested dataclasses from plain dicts
        claims = [
            Claim(
                id=c["id"],
                text=c["text"],
                tag=Tag(c["tag"]),
                source_ids=c.get("source_ids", []),
                supports=c.get("supports", []),
            )
            for c in data.get("claims", [])
        ]
        sources = [
            Source(id=s["id"], type=s["type"], ref=s["ref"], date=s["date"])
            for s in data.get("sources", [])
        ]
        timeline = [
            TimelineEntry(
                date=t["date"],
                event=t["event"],
                claim_ids=t.get("claim_ids", []),
            )
            for t in data.get("timeline", [])
        ]
        outcome = None
        if data.get("outcome"):
            o = data["outcome"]
            outcome = Outcome(
                summary=o["summary"],
                actors=o.get("actors", []),
                constraint_types=[ConstraintType(ct) for ct in o.get("constraint_types", [])],
                recorded_at=o.get("recorded_at"),
                sources=[
                    Source(id=s["id"], type=s["type"], ref=s["ref"], date=s["date"])
                    for s in o.get("sources", [])
                ],
            )
        return cls(
            incident_id=data["incident_id"],
            title=data["title"],
            status=Status(data["status"]),
            date=data["date"],
            recorded_at=data["recorded_at"],
            actors=data["actors"],
            actor_roles=data["actor_roles"],
            sector=data["sector"],
            geography=data["geography"],
            trigger=data["trigger"],
            trigger_type=TriggerType(data["trigger_type"]),
            constraint_types=[ConstraintType(ct) for ct in data.get("constraint_types", [])],
            legal_outcome=LegalOutcome(data["legal_outcome"]),
            escalation_vector=[EscalationVector(ev) for ev in data.get("escalation_vector", [])],
            tempo=Tempo(data["tempo"]),
            exit_authority=ExitAuthority(data["exit_authority"]),
            succession=Succession(data["succession"]),
            timeline=timeline,
            resolution=[Resolution(r) for r in data.get("resolution", [])],
            outcome=outcome,
            claims=claims,
            sources=sources,
            summary_embed=data.get("summary_embed", ""),
            unverified=data.get("unverified", False),
        )

    def validate(self) -> None:
        """Validate the card, raising ValueError listing bad fields."""
        errors: list[str] = []

        # Enum fields are already validated by the type system, but check
        # actor_roles against the closed vocabulary.
        for role in self.actor_roles:
            if role not in ACTOR_ROLES:
                errors.append(f"actor_roles: unknown role '{role}'")

        # constraint_types must be valid enum values (already enforced, but
        # check membership in precedence set)
        for ct in self.constraint_types:
            if ct not in CONSTRAINT_PRECEDENCE:
                errors.append(f"constraint_types: unknown value '{ct}'")

        # Claim ids must be c1..cn in order
        for i, claim in enumerate(self.claims, start=1):
            expected_id = f"c{i}"
            if claim.id != expected_id:
                errors.append(f"claims[{i-1}].id: expected '{expected_id}', got '{claim.id}'")

        # timeline claim_ids must reference existing claim ids
        claim_ids = {c.id for c in self.claims}
        for i, entry in enumerate(self.timeline):
            for cid in entry.claim_ids:
                if cid not in claim_ids:
                    errors.append(f"timeline[{i}].claim_ids: unknown claim reference '{cid}'")

        if errors:
            raise ValueError("Invalid incident card:\n  " + "\n  ".join(errors))


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------


def card_to_json(card: IncidentCard) -> str:
    """Serialize a card to JSON (pretty-printed, sorted keys)."""
    return json.dumps(card.to_dict(), indent=2, sort_keys=True, ensure_ascii=False)


def card_from_json(text: str) -> IncidentCard:
    """Deserialize a card from JSON, applying the load-time provenance
    downgrade (documented -> reported_unconfirmed if excerpt file absent)."""
    data = json.loads(text)
    card = IncidentCard.from_dict(data)

    # Load-time provenance downgrade: a documented claim whose excerpt file
    # is absent loads as reported_unconfirmed.
    source_refs = {s.id: s for s in card.sources}
    for claim in card.claims:
        if claim.tag == Tag.DOCUMENTED:
            has_excerpt = any(
                source_refs[sid].ref and Path(source_refs[sid].ref).exists()
                for sid in claim.source_ids
                if sid in source_refs
            )
            if not has_excerpt:
                claim.tag = Tag.REPORTED_UNCONFIRMED

    card.validate()
    return card


def load_card(path: str | Path) -> IncidentCard:
    """Load a card from a JSON file, applying the provenance downgrade."""
    return card_from_json(Path(path).read_text(encoding="utf-8"))


def save_card(card: IncidentCard, path: str | Path) -> None:
    """Save a card to a JSON file. Validates before writing."""
    card.validate()
    Path(path).write_text(card_to_json(card), encoding="utf-8")
