"""Gap detectors for the research loop.

Four mechanical gap types, each with a gap_type and gap_ref.
A question that cannot name its gap_type and gap_ref is never dispatched.
"""

from typing import Any
from dataclasses import dataclass
from typing import Optional

from .schema import IncidentCard
from .scoring import why_matches, where_breaks


@dataclass
class GapQuestion:
    question: str
    gap_type: str
    gap_ref: str
    # For dedupe: (gap_type, gap_ref) is the key
    # A question that cannot name its gap_type and gap_ref is never dispatched


# Fields where new evidence could change the classification (evidence-sensitive)
# Gap 3 is RESTRICTED to these fields only
EVIDENCE_SENSITIVE_FIELDS = (
    "trigger_type",
    "constraint_types",
    "escalation_vector",
)

# Fields excluded from gap 3 - determined by what happened, not by what you can look up
EXCLUDED_FROM_GAP_3 = (
    "exit_authority",
    "resolution",
    "tempo",
    "succession",
)


def generate_questions(card: IncidentCard) -> list[GapQuestion]:
    """Generate research questions from a card's gaps.

    Returns at most 5 questions (one per round max, deduplicated by (gap_type, gap_ref)).
    A question that cannot name its gap_type and gap_ref is never dispatched.
    """
    questions: list[GapQuestion] = []
    seen_keys: set[tuple[str, str]] = set()

    def add_question(q: str, gap_type: str, gap_ref: str) -> bool:
        """Add question if not duplicate. Returns True if added."""
        key = (gap_type, gap_ref)
        if key in seen_keys:
            return False
        seen_keys.add(key)
        questions.append(GapQuestion(question=q, gap_type=gap_type, gap_ref=gap_ref))
        return True

    # Gap 1: Missing structural fields (from SILENCE_FIELDS)
    from .match import SILENCE_FIELDS
    for field in SILENCE_FIELDS:
        val = getattr(card, field, None)
        if val is None or (isinstance(val, (list, str)) and not val):
            if add_question(
                f"What is the {field.replace('_', ' ')}?",
                "gap_1_missing_field",
                field,
            ):
                break  # One missing field per round max

    # Gap 2: Below-documented claims
    for claim in card.claims:
        if claim.tag != "documented":
            if add_question(
                f"What evidence supports the claim: {claim.text}?",
                "gap_2_below_documented",
                claim.id,
            ):
                break  # One below-documented claim per round max

    # Gap 3: Mismatch vs top match - RESTRICTED to evidence-sensitive fields
    # Only fields where new evidence could change the classification
    # Excluded: exit_authority, resolution, tempo, succession
    # (determined by what happened, not by what you can look up)
    # This prevents unanswerable questions about facts already established
    # if card.matches:  # would need matches passed in
    #     pass

    # Gap 4: New shape (no strong matches)
    # The one field that would disambiguate
    if not card.matches:  # placeholder - would check actual matches
        if add_question(
            "What event or field would disambiguate this new shape?",
            "gap_4_new_shape",
            "new_shape",
        ):
            pass

    return questions[:5]  # Max 5 questions per round


def filter_round_questions(questions: list[GapQuestion], round_num: int, previous_round_results: dict[str, Any]) -> list[GapQuestion]:
    """Filter questions for a round.

    - Round 1: all questions
    - Round 2: exclude questions that were answered with 'no source available' in round 1
    - Dedup by (gap_type, gap_ref) - duplicates don't count against cap
    """
    if round_num == 1:
        return questions[:5]

    # Build set of gap_refs that returned 'no source available' in round 1
    no_source_refs = set()
    for gap_ref, result in previous_round_results.items():
        if result.get("source") is None:
            no_source_refs.add(gap_ref)

    filtered = [q for q in questions if q.gap_ref not in no_source_refs]
    return filtered[:5]