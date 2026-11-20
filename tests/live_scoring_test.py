"""Live test: score Nvidia query card against all 24 corpus cards with real fastembed cosines.
Cosine is used only as a pre-filter (top 20 by cosine), then typed-field scoring ranks
the filtered set."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastembed import TextEmbedding

from incidents.schema import load_card, summary_embed_template
from incidents.scoring import score, calibrate_weak_floor

DATA_DIR = Path("data/incidents")
QUERY_PATH = Path("tests/fixtures/query_nvidia_analog.json")

embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")


def embed(text: str) -> list[float]:
    return list(embedder.embed([text]))[0]


def cosine(a: list[float], b: list[float]) -> float:
    import math

    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def percentile(sorted_scores: list[float], pct: float) -> float:
    """Linear interpolation percentile."""
    n = len(sorted_scores)
    if n == 1:
        return sorted_scores[0]
    idx = pct * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sorted_scores[lo] + frac * (sorted_scores[hi] - sorted_scores[lo])


def main():
    # Load query card
    query_card = load_card(QUERY_PATH)
    query_embed = embed(summary_embed_template(query_card.to_dict()))

    # Load all corpus cards with cosine
    corpus_cards = []
    for path in sorted(DATA_DIR.glob("*.json")):
        if path.name == "_corpus_list.md":
            continue
        card = load_card(path)
        card_embed = embed(summary_embed_template(card.to_dict()))
        c = cosine(query_embed, card_embed)
        corpus_cards.append((card, c))

    # Cosine as pre-filter: top 20 by cosine
    corpus_cards.sort(key=lambda x: x[1], reverse=True)
    filtered = corpus_cards[:20]
    print(f"Corpus size: {len(corpus_cards)}, filtering to top {len(filtered)} by cosine")

    # Score on filtered set
    results = []
    for card, cos in filtered:
        result = score(query_card, card)
        results.append((card, cos, result["score"], result["components"]))

    # Rank by score descending
    results.sort(key=lambda x: x[2], reverse=True)

    # Weak floor from live scores (60th percentile)
    raw_scores_only = [s for _, _, s, _ in results]
    weak_floor = calibrate_weak_floor(raw_scores_only)

    # Print raw table
    print("=== RAW COSINE SCORES (cosine as filter only) ===")
    print(f"{'Rank':<6} {'Card ID':<32} {'Cosine':<8} {'Score':<8} {'Tier':<8} {'Top 2 why_matches':<45} {'Top 2 where_breaks':<45}")
    print("-" * 160)
    for i, (card, cos, s, comps) in enumerate(results, 1):
        tier = "strong" if s >= weak_floor else "weak"
        wm = [f"{k}({v['value']:.2f})" for k, v in sorted(comps.items(), key=lambda x: x[1]["contribution"], reverse=True) if v["value"] > 0][:2]
        wb = [f"{k}({v['value']:.2f})" for k, v in sorted(comps.items(), key=lambda x: x[1]["weight"], reverse=True) if v["value"] == 0][:2]
        print(f"{i:<6} {card.incident_id:<32} {cos:<8.4f} {s:<8.4f} {tier:<8} {str(wm):<45} {str(wb):<45}")

    # Distribution stats
    sorted_scores = sorted(raw_scores_only)
    print(f"\nLive-score distribution:")
    print(f"  min={sorted_scores[0]:.4f}  p25={percentile(sorted_scores, 0.25):.4f}  p50={percentile(sorted_scores, 0.50):.4f}  p75={percentile(sorted_scores, 0.75):.4f}  max={sorted_scores[-1]:.4f}")
    print(f"Weak floor (60th percentile of live scores): {weak_floor:.4f}")
    n_strong = sum(1 for _, _, s, _ in results if s >= weak_floor)
    print(f"Cards clearing threshold: {n_strong} of {len(results)}")

    # Component breakdown for top 5
    print("\n" + "=" * 120)
    print("TOP 5 COMPONENT BREAKDOWN (unrounded):")
    print("=" * 120)
    for i, (card, cos, s, comps) in enumerate(results[:5], 1):
        print(f"\n#{i} {card.incident_id} (score={s:.6f}, cosine={cos:.6f})")
        for comp_name in ["trigger_type", "roles", "constraint", "escalation", "resolution", "tempo", "exit_authority", "outcome"]:
            comp = comps[comp_name]
            print(f"  {comp_name:<16} value={comp['value']:.6f}  weight={comp['weight']:.2f}  contrib={comp['contribution']:.6f}")

    print(f"\nQuery card: {query_card.incident_id} ({query_card.title})")
    print(f"Query trigger_type: {query_card.trigger_type.value}")
    print(f"Query exit_authority: {query_card.exit_authority.value}")
    print(f"Query succession: {query_card.succession.value}")
    print(f"Query constraint_types: {[c.value for c in query_card.constraint_types]}")
    print(f"Query tempo: {query_card.tempo.value}")


if __name__ == "__main__":
    main()
