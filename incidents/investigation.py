"""Question-driven 'mini CID' investigator — v6 architecture.

Entry point: ``investigate(question)`` replaces ``run_match(paste)`` as the
primary flow. Instead of requiring the user to paste an incident summary
(which assumes the user already did the fact-finding), the system starts
from a plain question and investigates it like a lean 'mini CID' agency.

Six investigative perspectives (questions, not personas):

    Money:     Who paid, who benefited, who lost?      (filings, contracts, funding, EDGAR)
    Power:     Who appointed, who could remove, who protected?  (board records, appointments, regulators)
    Secrecy:   What is reported but unconfirmed? Who won't comment?  (press, denials, unnamed sources)
    Timing:    What changed in the weeks before?  (dated news, event timelines)
    Network:   Who else is connected to these people or firms?  (company registries, sanctions lists)
    Counter-case: What would have to be true for the official story to be whole?  (adversarial queries)

Cost & token discipline: free search/data sources via sources.py returning
{title, url, snippet, date}; mechanical regex/gazetteer extraction for
dates/names/amounts; typed structural matching (scoring.py, schema v6 with
external_pressure); one bounded LLM synthesis call (~1–2k tokens total).

Honesty & provenance: every claim keeps its provenance tag (documented only
with a real source artifact + verbatim quote; otherwise
reported_unconfirmed / inferred / speculative).
"""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from .schema import (
    IncidentCard,
    Tag,
    apply_tag_cascade,
)
from .scoring import score, WEIGHTS_VERSION, tier_label
from .sources import (
    search_money,
    search_power,
    search_secrecy,
    search_timing,
    search_network,
    search_counter_case,
    extract_dates,
    extract_amounts,
    extract_names,
)

try:  # pragma: no cover - config is always present at runtime
    from vg.config import config as _vg_config
except Exception:  # pragma: no cover
    _vg_config = None  # type: ignore[assignment]

# Token ceiling for the single bounded LLM synthesis call (~1-2k tokens total)
SYNTHESIS_MAX_TOKENS = 1500

# Valid provenance tags
VALID_TAGS = {"documented", "reported_unconfirmed", "inferred", "speculative"}


# ---------------------------------------------------------------------------
# Mechanical entity extraction from a question
# ---------------------------------------------------------------------------

_ENTITY_PATTERNS = [
    re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:CEO|CFO|founder|chairman|chairperson|president|minister|director)\b"),
    re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Inc|Corp|Corporation|Ltd|Limited|LLC|PLC|Group|Bank|Banking)\b"),
]


def _extract_entities(question: str) -> list[str]:
    """Extract person/entity names from a question using gazetteer patterns."""
    entities: list[str] = []
    for pattern in _ENTITY_PATTERNS:
        for m in pattern.finditer(question):
            name = m.group(1)
            if name not in entities:
                entities.append(name)
    # Fallback: any capitalised multi-word phrase
    if not entities:
        for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", question):
            name = m.group(0)
            if name not in entities:
                entities.append(name)
    return entities[:5]  # Cap at 5 entities


def _extract_dates_amounts(question: str) -> dict[str, list[str]]:
    """Extract dates and amounts from a question."""
    return {
        "dates": extract_dates(question),
        "amounts": extract_amounts(question),
    }


# ---------------------------------------------------------------------------
# Six investigative lenses
# ---------------------------------------------------------------------------

_LENS_FUNCS = {
    "money": search_money,
    "power": search_power,
    "secrecy": search_secrecy,
    "timing": search_timing,
    "network": search_network,
    "counter_case": search_counter_case,
}


def _run_lens(lens_name: str, entities: list[str], dates_amounts: dict[str, list[str]], question: str) -> dict[str, Any]:
    """Run one investigative lens against extracted entities.

    Returns {'queries': [...], 'findings': [...]} where each finding has
    {title, url, snippet, date, tag, lens, question}. Mechanical question
    extractions (entities/dates/amounts) live once in ``question_profile``
    instead of being repeated into every lens.
    """
    queries: list[str] = []
    findings: list[dict[str, Any]] = []

    search_fn = _LENS_FUNCS[lens_name]
    for entity in entities:
        results = search_fn(entity)
        for r in results:
            queries.append(r.get("query", ""))
            # Use tag from source if present (e.g., "inferred" for structured data),
            # otherwise default to "reported_unconfirmed" for free web search
            tag = r.get("tag", "reported_unconfirmed")
            findings.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("snippet", ""),
                "date": r.get("date", ""),
                "tag": tag,
                "lens": lens_name,
                "question": r.get("query", ""),
            })

    return {"queries": queries, "findings": findings}


def question_snippet(question: str, term: str) -> str:
    """Return a snippet of the question around a term."""
    idx = question.lower().find(term.lower())
    if idx < 0:
        return question[:100]
    start = max(0, idx - 30)
    end = min(len(question), idx + len(term) + 30)
    return question[start:end]


# ---------------------------------------------------------------------------
# Contradiction detection across lenses
# ---------------------------------------------------------------------------

def _detect_contradictions(lens_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect contradictions across the six investigative lenses.

    Looks for opposing claims about the same entity/topic across different
    lenses (e.g., money says X benefited, power says Y appointed).
    """
    contradictions: list[dict[str, Any]] = []

    # Collect all findings by lens
    lens_findings = {
        lens: data.get("findings", [])
        for lens, data in lens_results.items()
    }

    # Simple contradiction detection: findings with opposing keywords
    # across different lenses about similar entities
    denial_keywords = {"denied", "unconfirmed", "unsubstantiated", "false", "baseless"}
    affirmation_keywords = {"confirmed", "admitted", "acknowledged", "revealed", "established"}

    for lens_a, findings_a in lens_findings.items():
        for lens_b, findings_b in lens_findings.items():
            if lens_a >= lens_b:
                continue  # Avoid duplicate pairs
            for fa in findings_a:
                for fb in findings_b:
                    fa_text = (fa.get("snippet", "") + " " + fa.get("title", "")).lower()
                    fb_text = (fb.get("snippet", "") + " " + fb.get("title", "")).lower()
                    fa_has_denial = any(k in fa_text for k in denial_keywords)
                    fb_has_affirmation = any(k in fb_text for k in affirmation_keywords)
                    fa_has_affirmation = any(k in fa_text for k in affirmation_keywords)
                    fb_has_denial = any(k in fb_text for k in denial_keywords)

                    if (fa_has_denial and fb_has_affirmation) or (fa_has_affirmation and fb_has_denial):
                        contradictions.append({
                            "lens_a": lens_a,
                            "lens_b": lens_b,
                            "finding_a": fa.get("title", "")[:80],
                            "finding_b": fb.get("title", "")[:80],
                            "type": "denial_vs_affirmation",
                        })

    return contradictions


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def _apply_corroboration(lens_results: dict[str, dict[str, Any]]) -> None:
    """Tag every finding with how many lenses surfaced the same source.

    The same article often matches several lens queries. Counting the lenses
    that found it is a free strength signal: three lenses on one URL means
    the story is cross-cutting, not incidental.
    """
    counts: dict[str, int] = {}
    for data in lens_results.values():
        for finding in data.get("findings", []):
            url = finding.get("url")
            if url:
                counts[url] = counts.get(url, 0) + 1

    for data in lens_results.values():
        for finding in data.get("findings", []):
            finding["corroboration"] = counts.get(finding.get("url", ""), 1)


def investigate(question: str) -> dict[str, Any]:
    """Investigate a question using six lenses and return findings.

    Args:
        question: A plain-language question (e.g., "Why did the CEO resign?")

    Returns:
        Dict with keys:
            question: the input question
            lens_results: {lens_name: {"queries": [...], "findings": [...]}} for six lenses
            question_profile: {"entities": [...], "dates": [...], "amounts": [...]}
            synthesis: bounded LLM synthesis string (~1-2k tokens)
            provenance: tag summary across all findings
            contradictions: list of cross-lens contradictions
    """
    # Extract entities, dates, amounts from the question
    entities = _extract_entities(question)
    dates_amounts = _extract_dates_amounts(question)

    # Run all six lenses
    lens_results: dict[str, dict[str, Any]] = {}
    for lens_name in _LENS_FUNCS:
        lens_results[lens_name] = _run_lens(lens_name, entities, dates_amounts, question)

    # Mark how many lenses surfaced each source
    _apply_corroboration(lens_results)

    # Detect contradictions across lenses
    contradictions = _detect_contradictions(lens_results)

    # Build provenance summary
    all_findings = [
        f for data in lens_results.values() for f in data.get("findings", [])
    ]
    tag_counts: dict[str, int] = {}
    unique_urls: set[str] = set()
    for f in all_findings:
        tag = f.get("tag", "speculative")
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
        if f.get("url"):
            unique_urls.add(f["url"])

    # Bounded LLM synthesis call (placeholder — actual LLM call would go here)
    synthesis = _synthesize(question, lens_results, contradictions)

    return {
        "question": question,
        "lens_results": lens_results,
        "question_profile": {
            "entities": entities,
            "dates": dates_amounts["dates"],
            "amounts": dates_amounts["amounts"],
        },
        "synthesis": synthesis,
        "provenance": {
            "total_findings": len(all_findings),
            "unique_sources": len(unique_urls),
            "tag_counts": tag_counts,
            "lenses_run": list(_LENS_FUNCS.keys()),
        },
        "contradictions": contradictions,
    }


def _synthesize(question: str, lens_results: dict[str, dict[str, Any]], contradictions: list[dict[str, Any]]) -> str:
    """Bounded LLM synthesis call (~1-2k tokens total).

    Currently returns a mechanical synthesis without an actual LLM call,
    keeping within the token ceiling. The synthesis summarises findings
    across lenses and flags contradictions.
    """
    total_findings = sum(len(d.get("findings", [])) for d in lens_results.values())
    num_contradictions = len(contradictions)

    parts = [
        f"Investigation of: {question}",
        f"Lenses run: {', '.join(sorted(lens_results.keys()))}",
        f"Total findings: {total_findings}",
        f"Contradictions detected: {num_contradictions}",
    ]

    # Add per-lens summary
    for lens_name in sorted(lens_results.keys()):
        data = lens_results[lens_name]
        n_findings = len(data.get("findings", []))
        n_queries = len(data.get("queries", []))
        if n_findings > 0 or n_queries > 0:
            parts.append(f"  {lens_name}: {n_findings} findings from {n_queries} queries")

    # Add contradiction summary
    if contradictions:
        parts.append("Contradictions:")
        for c in contradictions[:5]:  # Cap at 5 for brevity
            parts.append(f"  {c['lens_a']} vs {c['lens_b']}: {c['type']}")

    synthesis = "\n".join(parts)

    # Enforce token ceiling (~1-2k tokens ≈ ~1500-2000 chars for English)
    if len(synthesis) > SYNTHESIS_MAX_TOKENS:
        synthesis = synthesis[:SYNTHESIS_MAX_TOKENS] + "\n[truncated]"

    return synthesis
