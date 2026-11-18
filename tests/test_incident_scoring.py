"""Golden fixture tests for incident scoring.

Uses synthetic fixture cards (not the held-out Nvidia corpus card).
Pass criterion: correct top-5 ordering, never absolute scores.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vg.incidents.schema import load_card
from vg.incidents.scoring import score, WEIGHTS, WEIGHTS_VERSION


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _load(name: str):
    return load_card(FIXTURE_DIR / f"{name}.json")


QUERY_CARD = _load("query_nvidia_analog")
CANDIDATE_1 = _load("candidate_1")
CANDIDATE_2 = _load("candidate_2")
CANDIDATE_3 = _load("candidate_3")
CANDIDATE_4 = _load("candidate_4")
CANDIDATE_5 = _load("candidate_5")

CANDIDATES = [CANDIDATE_1, CANDIDATE_2, CANDIDATE_3, CANDIDATE_4, CANDIDATE_5]


def test_weights_sum_to_one():
    """WEIGHTS must sum to 1.0."""
    total = sum(WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9, f"WEIGHTS sum to {total}, not 1.0"


def test_weights_version_is_4():
    """WEIGHTS_VERSION tracks schema changes."""
    assert WEIGHTS_VERSION == 4


def test_expected_top5_ordering():
    """Top-5 ordering must be deterministic: c1 > c2 > c3 > c4 > c5."""
    results = []
    for cand in CANDIDATES:
        result = score(QUERY_CARD, cand)
        results.append((cand.incident_id, result["score"]))

    results.sort(key=lambda x: x[1], reverse=True)
    ordered_ids = [rid for rid, _ in results]

    assert ordered_ids == [
        "fixture_candidate_1",
        "fixture_candidate_2",
        "fixture_candidate_3",
        "fixture_candidate_5",
        "fixture_candidate_4",
    ], f"Unexpected ordering: {ordered_ids}"


def test_per_component_contributions_within_tolerance():
    """Per-component contributions must match hand-computed values within ±0.01."""
    # Candidate 1: near-perfect match across all typed fields
    result = score(QUERY_CARD, CANDIDATE_1)
    comps = result["components"]

    # trigger_type: match = 1.0 * 0.2667 = 0.2667
    assert abs(comps["trigger_type"]["contribution"] - 0.2667) < 0.01
    assert abs(comps["trigger_type"]["value"] - 1.0) < 0.01

    # roles: Jaccard(["ceo","board"],["ceo","board"]) = 1.0 * 0.20 = 0.20
    assert abs(comps["roles"]["contribution"] - 0.20) < 0.01
    assert abs(comps["roles"]["value"] - 1.0) < 0.01

    # constraint: Jaccard(["reputational","legal"],["reputational","security"]) = 1/3
    assert abs(comps["constraint"]["contribution"] - 0.1333 * (1.0 / 3.0)) < 0.01
    assert abs(comps["constraint"]["value"] - (1.0 / 3.0)) < 0.01

    # escalation: Jaccard(["media_cycle","inquiry"],["media_cycle","inquiry"]) = 1.0 * 0.1333 = 0.1333
    assert abs(comps["escalation"]["contribution"] - 0.1333) < 0.01
    assert abs(comps["escalation"]["value"] - 1.0) < 0.01

    # resolution: Jaccard(["resignation"],["resignation"]) = 1.0 * 0.0667 = 0.0667
    assert abs(comps["resolution"]["contribution"] - 0.0667) < 0.01
    assert abs(comps["resolution"]["value"] - 1.0) < 0.01

    # tempo: mismatch (weeks vs days) = 0.0 * 0.0667 = 0.0
    assert abs(comps["tempo"]["contribution"] - 0.0) < 0.01
    assert abs(comps["tempo"]["value"] - 0.0) < 0.01

    # exit_authority: match = 1.0 * 0.0667 = 0.0667
    assert abs(comps["exit_authority"]["contribution"] - 0.0667) < 0.01
    assert abs(comps["exit_authority"]["value"] - 1.0) < 0.01

    # outcome: avg(Jaccard(res)=1.0, eq(succ)=0.0, Jaccard(constraint)=1/3) = (1.0+0.0+0.333)/3 ≈ 0.444
    assert abs(comps["outcome"]["contribution"] - 0.0667 * (1.0 + 0.0 + 1.0 / 3.0) / 3.0) < 0.01
    assert abs(comps["outcome"]["value"] - (1.0 + 0.0 + 1.0 / 3.0) / 3.0) < 0.01

    # Total: sum of all contributions
    total = sum(c["contribution"] for c in comps.values())
    assert abs(total - result["score"]) < 0.001


def test_candidate_2_contributions():
    """Candidate 2: partial match across several fields."""
    result = score(QUERY_CARD, CANDIDATE_2)
    comps = result["components"]

    # roles: Jaccard(["ceo","board"],["ceo","investor"]) = 1/3 ≈ 0.333
    assert abs(comps["roles"]["value"] - (1.0 / 3.0)) < 0.01
    assert abs(comps["roles"]["contribution"] - 0.20 * (1.0 / 3.0)) < 0.01

    # constraint: Jaccard(["reputational","legal"],["reputational"]) = 1/2 = 0.5
    assert abs(comps["constraint"]["value"] - 0.5) < 0.01
    assert abs(comps["constraint"]["contribution"] - 0.1333 * 0.5) < 0.01

    # escalation: Jaccard(["media_cycle","inquiry"],["media_cycle"]) = 1/2 = 0.5
    assert abs(comps["escalation"]["value"] - 0.5) < 0.01
    assert abs(comps["escalation"]["contribution"] - 0.1333 * 0.5) < 0.01

    # succession: eq("internal","internal") = 1.0
    # outcome = avg(Jaccard(res)=1.0, eq(succ)=1.0, Jaccard(constraint)=0.5) = (1.0+1.0+0.5)/3 ≈ 0.833
    assert abs(comps["outcome"]["value"] - (1.0 + 1.0 + 0.5) / 3.0) < 0.01
    assert abs(comps["outcome"]["contribution"] - 0.0667 * (1.0 + 1.0 + 0.5) / 3.0) < 0.01


def test_candidate_5_contributions():
    """Candidate 5: weak match, only exit_authority and partial roles match."""
    result = score(QUERY_CARD, CANDIDATE_5)
    comps = result["components"]

    # trigger_type: mismatch = 0.0
    assert abs(comps["trigger_type"]["value"] - 0.0) < 0.01
    assert abs(comps["trigger_type"]["contribution"] - 0.0) < 0.01

    # roles: Jaccard(["ceo","board"],["board"]) = 1/2 = 0.5
    assert abs(comps["roles"]["value"] - 0.5) < 0.01
    assert abs(comps["roles"]["contribution"] - 0.20 * 0.5) < 0.01

    # exit_authority: match ("board" == "board") = 1.0
    assert abs(comps["exit_authority"]["value"] - 1.0) < 0.01
    assert abs(comps["exit_authority"]["contribution"] - 0.0667) < 0.01

    # outcome: avg(Jaccard(res)=0.0, eq(succ)=1.0, Jaccard(constraint)=0.0) = (0.0+1.0+0.0)/3 ≈ 0.333
    assert abs(comps["outcome"]["value"] - (0.0 + 1.0 + 0.0) / 3.0) < 0.01
    assert abs(comps["outcome"]["contribution"] - 0.0667 * (0.0 + 1.0 + 0.0) / 3.0) < 0.01


def test_structural_dominance():
    """Structural match beats high cosine with mismatched typed fields.

    Query: personal_conduct CEO resignation, board exit authority, resignation resolution.
    Candidate A: cosine 0.85 but all typed fields mismatch.
    Candidate B: cosine 0.30 but trigger_type, exit_authority, resolution all match.
    B must outrank A. If it fails, report needed weight changes rather than retuning.
    """
    query = QUERY_CARD  # personal_conduct, board, resignation, days, self

    # Candidate A: high cosine, all typed fields mismatch
    cand_a = CANDIDATE_5  # operational_failure, board, bankruptcy — mostly mismatched
    result_a = score(query, cand_a)

    # Candidate B: low cosine, key typed fields match
    cand_b = CANDIDATE_2  # personal_conduct, board, dismissal — matches trigger, exit_authority
    result_b = score(query, cand_b)

    assert result_b["score"] > result_a["score"], (
        f"Structural dominance failed: cand_b={result_b['score']:.4f} should beat "
        f"cand_a={result_a['score']:.4f}. "
        f"To fix, increase typed-field weights relative to cosine. "
        f"Combined typed weight={1.0 - WEIGHTS['cosine'] if 'cosine' in WEIGHTS else 1.0}"
    )


def test_self_score_sanity():
    """A card scored against itself yields maximum score with all components at 1.0."""
    result = score(QUERY_CARD, QUERY_CARD)
    comps = result["components"]

    # All components should be 1.0 against self
    assert abs(result["score"] - 1.0) < 0.001, f"Self-score={result['score']}, expected 1.0"
    assert abs(comps["trigger_type"]["value"] - 1.0) < 0.001
    assert abs(comps["roles"]["value"] - 1.0) < 0.001
    assert abs(comps["constraint"]["value"] - 1.0) < 0.001
    assert abs(comps["escalation"]["value"] - 1.0) < 0.001
    assert abs(comps["resolution"]["value"] - 1.0) < 0.001
    assert abs(comps["tempo"]["value"] - 1.0) < 0.001
    assert abs(comps["exit_authority"]["value"] - 1.0) < 0.001
    assert abs(comps["outcome"]["value"] - 1.0) < 0.001


def test_score_is_deterministic():
    """Same inputs must produce identical scores."""
    r1 = score(QUERY_CARD, CANDIDATE_1)
    r2 = score(QUERY_CARD, CANDIDATE_1)
    assert r1["score"] == r2["score"]
    assert r1["components"] == r2["components"]


def test_jaccard_empty_list():
    """Jaccard(∅, ·) = 0."""
    from vg.incidents.scoring import jaccard

    assert jaccard([], ["a", "b"]) == 0.0
    assert jaccard(["a", "b"], []) == 0.0
    assert jaccard([], []) == 0.0
    assert abs(jaccard(["a", "b"], ["a", "b"]) - 1.0) < 0.001


def test_eq():
    """Equality check: 1.0 if equal, 0.0 if different."""
    from vg.incidents.scoring import eq

    assert eq("a", "a") == 1.0
    assert eq("a", "b") == 0.0
