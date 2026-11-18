"""Pure scoring functions for incident structural matching.

No I/O, no LLM, no Chroma imports. Cosine is NOT part of the score -- it is
used only as a pre-filter (embed query and candidates, take top N by cosine,
then rank those N on the eight typed-field components below).

Reason: same-domain incident text saturates bge-small at ~0.95 cosine, so
cosine cannot discriminate between structural shapes. It is useful only for
candidate pruning before typed-field scoring.

Scoring is deterministic given (card, candidate). Eight weighted components
sum to 1.0:

    0.2667 trigger_type    (equality)
    0.2000 roles-Jaccard     (actor_roles list)
    0.1333 constraint-Jaccard (constraint_types list)
    0.1333 escalation-Jaccard (escalation_vector list)
    0.0667 resolution        (resolution list Jaccard)
    0.0667 tempo             (equality)
    0.0667 exit_authority    (equality)
    0.0667 outcome-Jaccard   (resolution + succession + constraint_types Jaccard)
"""

from __future__ import annotations

from typing import Any

from .schema import IncidentCard

WEIGHTS = {
    "trigger_type": 0.20 / 0.75,   # 0.2667
    "roles": 0.15 / 0.75,          # 0.2000
    "constraint": 0.10 / 0.75,     # 0.1333
    "escalation": 0.10 / 0.75,     # 0.1333
    "resolution": 0.05 / 0.75,     # 0.0667
    "tempo": 0.05 / 0.75,          # 0.0667
    "exit_authority": 0.05 / 0.75, # 0.0667
    "outcome": 0.05 / 0.75,        # 0.0667
}

WEIGHTS_VERSION = 4

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "WEIGHTS must sum to 1.0"


def jaccard(a: list, b: list) -> float:
    """Jaccard similarity between two lists. Jaccard(∅, ·) = 0."""
    set_a = set(a)
    set_b = set(b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def eq(a: Any, b: Any) -> float:
    """Equality check: 1.0 if equal, 0.0 if different."""
    return 1.0 if a == b else 0.0


def score(card: IncidentCard, candidate: IncidentCard) -> dict:
    """Deterministic score given (card, candidate).

    Returns a dict with the total score and per-component contributions.
    Cosine is NOT included -- it is used only as a pre-filter.
    """
    components = {}

    # trigger_type (equality)
    t_val = eq(card.trigger_type.value, candidate.trigger_type.value)
    components["trigger_type"] = {
        "weight": WEIGHTS["trigger_type"],
        "value": t_val,
        "contribution": WEIGHTS["trigger_type"] * t_val,
    }

    # roles-Jaccard
    r_val = jaccard(list(card.actor_roles), list(candidate.actor_roles))
    components["roles"] = {
        "weight": WEIGHTS["roles"],
        "value": r_val,
        "contribution": WEIGHTS["roles"] * r_val,
    }

    # constraint-Jaccard
    c_card = [ct.value for ct in card.constraint_types]
    c_cand = [ct.value for ct in candidate.constraint_types]
    c_val_j = jaccard(c_card, c_cand)
    components["constraint"] = {
        "weight": WEIGHTS["constraint"],
        "value": c_val_j,
        "contribution": WEIGHTS["constraint"] * c_val_j,
    }

    # escalation-Jaccard
    e_card = [ev.value for ev in card.escalation_vector]
    e_cand = [ev.value for ev in candidate.escalation_vector]
    e_val_j = jaccard(e_card, e_cand)
    components["escalation"] = {
        "weight": WEIGHTS["escalation"],
        "value": e_val_j,
        "contribution": WEIGHTS["escalation"] * e_val_j,
    }

    # resolution (Jaccard on resolution list)
    r_card = [r.value for r in card.resolution]
    r_cand = [r.value for r in candidate.resolution]
    r_val_j = jaccard(r_card, r_cand)
    components["resolution"] = {
        "weight": WEIGHTS["resolution"],
        "value": r_val_j,
        "contribution": WEIGHTS["resolution"] * r_val_j,
    }

    # tempo (equality)
    t_val = eq(card.tempo.value, candidate.tempo.value)
    components["tempo"] = {
        "weight": WEIGHTS["tempo"],
        "value": t_val,
        "contribution": WEIGHTS["tempo"] * t_val,
    }

    # exit_authority (equality)
    e_val = eq(card.exit_authority.value, candidate.exit_authority.value)
    components["exit_authority"] = {
        "weight": WEIGHTS["exit_authority"],
        "value": e_val,
        "contribution": WEIGHTS["exit_authority"] * e_val,
    }

    # outcome-Jaccard (average of Jaccard on resolution, succession,
    # constraint_types — typed fields only, never free text)
    o_card = (
        [r.value for r in card.resolution]
        + [card.succession.value]
        + [ct.value for ct in card.constraint_types]
    )
    o_cand = (
        [r.value for r in candidate.resolution]
        + [candidate.succession.value]
        + [ct.value for ct in candidate.constraint_types]
    )
    # Compute per-field Jaccard and average
    r_j = jaccard([r.value for r in card.resolution], [r.value for r in candidate.resolution])
    s_j = eq(card.succession.value, candidate.succession.value)
    c_j = jaccard([ct.value for ct in card.constraint_types], [ct.value for ct in candidate.constraint_types])
    o_val = (r_j + s_j + c_j) / 3.0
    components["outcome"] = {
        "weight": WEIGHTS["outcome"],
        "value": o_val,
        "contribution": WEIGHTS["outcome"] * o_val,
    }

    total_score = sum(comp["contribution"] for comp in components.values())

    return {
        "score": total_score,
        "components": components,
        "weights_version": WEIGHTS_VERSION,
    }


def why_matches(score_result: dict) -> list[dict]:
    """Mechanical why-matches: shared/equal typed fields weighted by contribution."""
    matches = []
    for name, comp in score_result["components"].items():
        if comp["value"] > 0:
            matches.append({
                "component": name,
                "weight": comp["weight"],
                "value": comp["value"],
                "contribution": comp["contribution"],
            })
    return sorted(matches, key=lambda m: m["contribution"], reverse=True)


def where_breaks(score_result: dict) -> list[dict]:
    """Mechanical where-it-breaks: mismatched or missing fields."""
    breaks = []
    for name, comp in score_result["components"].items():
        if comp["value"] == 0:
            breaks.append({
                "component": name,
                "weight": comp["weight"],
                "value": comp["value"],
                "contribution": 0.0,
            })
    return sorted(breaks, key=lambda b: b["weight"], reverse=True)


def tier_label(score: float, weak_threshold: float) -> str:
    """Tier label: strong if score >= threshold, weak otherwise."""
    return "strong" if score >= weak_threshold else "weak"


def calibrate_weak_floor(scores: list[float], percentile: float = 0.60) -> float:
    """Given a list of live match scores, return the percentile-th ranked score
    as the weak floor. This approximates the threshold at which a match would
    be considered "strong".

    scores: list of score floats, one per corpus card vs the query card.
    percentile: fraction in [0,1]. 0.50 = median, 0.60 = 60th percentile.
    """
    if len(scores) < 2:
        return 0.45

    scores.sort()
    n = len(scores)
    idx = max(0, min(n - 1, int(n * percentile)))
    return scores[idx]
