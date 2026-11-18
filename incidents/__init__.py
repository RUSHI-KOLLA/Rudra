"""VG incidents package — zero-agent structural incident memory.

Public surface: schema types, store functions, match orchestration entry.

Imports from the rest of the repo are limited to ``vg.config``,
``vg.core.llm_client``, and ``vg.search.web`` (search only).
"""

from .schema import (
    IncidentCard,
    Claim,
    Source,
    Outcome,
    TimelineEntry,
    Tag,
    TriggerType,
    ConstraintType,
    LegalOutcome,
    EscalationVector,
    Tempo,
    ExitAuthority,
    Succession,
    Resolution,
    Status,
    ACTOR_ROLES,
    summary_embed_template,
    load_card,
    save_card,
)

from .store import (
    record_hash,
    rebuild_index,
    load_all_cards,
    save_card_json,
    card_path,
)

__all__ = [
    # Schema
    "IncidentCard",
    "Claim",
    "Source",
    "Outcome",
    "TimelineEntry",
    "Tag",
    "TriggerType",
    "ConstraintType",
    "LegalOutcome",
    "EscalationVector",
    "Tempo",
    "ExitAuthority",
    "Succession",
    "Resolution",
    "ACTOR_ROLES",
    "summary_embed_template",
    "load_card",
    "save_card",
    # Store
    "record_hash",
    "rebuild_index",
    "load_all_cards",
    "save_card_json",
    "card_path",
]
