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
dates/names/amounts; one bounded LLM synthesis call (~1–2k tokens total).

Honesty & provenance: every claim keeps its provenance tag (documented only
with a real source artifact + verbatim quote; otherwise
reported_unconfirmed / inferred / speculative).
"""

from __future__ import annotations

import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .sources import (
    search_money,
    search_power,
    search_secrecy,
    search_timing,
    search_network,
    search_counter_case,
    extract_dates,
    extract_amounts,
)

# Token ceiling for the single bounded LLM synthesis call (~1-2k tokens total)
SYNTHESIS_MAX_TOKENS = 1500

# Test mode detection - the LLM synthesis path must stay off during tests
_IN_TEST = "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") is not None

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


#: Only web URLs are passed through to clients — a source must not be able to
#: smuggle a javascript:/data: URL into a rendered link.
_SAFE_URL_PREFIXES = ("http://", "https://")


def _is_safe_url(url: str) -> bool:
    """True when a URL is empty (no link) or an http(s) URL."""
    if not url:
        return True
    return url.lower().startswith(_SAFE_URL_PREFIXES)


def _run_lens(lens_name: str, entities: list[str], dates_amounts: dict[str, list[str]], question: str) -> dict[str, Any]:
    """Run one investigative lens against extracted entities.

    Returns {'queries': [...], 'findings': [...]} where each finding has
    {title, url, snippet, date, tag, lens, question}. Mechanical question
    extractions (entities/dates/amounts) live once in ``question_profile``
    instead of being repeated into every lens.

    A lens that raises is isolated: its error is recorded and the other
    lenses still report. One broken source must not void the investigation.
    """
    queries: list[str] = []
    findings: list[dict[str, Any]] = []
    seen_queries: set[str] = set()

    search_fn = _LENS_FUNCS[lens_name]
    for entity in entities:
        try:
            results = search_fn(entity)
        except Exception as exc:
            return {
                "queries": queries,
                "findings": findings,
                "error": f"{type(exc).__name__}: {exc}",
            }
        for r in results:
            url = str(r.get("url", "") or "")
            if not _is_safe_url(url):
                continue
            query = r.get("query", "")
            if query and query not in seen_queries:
                seen_queries.add(query)
                queries.append(query)
            # Use tag from source if present (e.g., "inferred" for structured data),
            # otherwise default to "reported_unconfirmed" for free web search
            tag = r.get("tag", "reported_unconfirmed")
            findings.append({
                "title": r.get("title", ""),
                "url": url,
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

#: Words that reverse a claim.
_NEGATION_TERMS = (
    "denied", "denies", "deny", "quashed", "rejected", "reversed", "cleared",
    "dismissed", "refuted", "false", "baseless", "unsubstantiated", "unconfirmed",
)

#: Words that assert a claim.
_AFFIRMATION_TERMS = (
    "confirmed", "admits", "admitted", "acknowledged", "upheld", "approved",
    "revealed", "established", "convicted", "indicted",
)

#: Capitalised words that can stand as the subject of a claim.
_SUBJECT_RE = re.compile(r"\b[A-Z][a-z]{3,}\b")

#: Capitalised words that are never a useful subject (interrogatives, news filler).
_SUBJECT_STOPWORDS = frozenset({
    "what", "when", "where", "which", "their", "there", "these", "those",
    "after", "before", "during", "report", "reports", "latest", "update",
    "updates", "breaking", "under", "about", "against", "following",
    "meanwhile", "since", "until", "while", "could", "would", "should",
    "because", "however", "although", "despite", "through", "between",
})

#: Procedural objects of a legal case. Two findings that both talk about the
#: law but name *different* objects ("sanction to prosecute" vs "attachment of
#: a flat") are parallel developments, not opposing claims.
_LEGAL_OBJECTS = frozenset({
    "sanction", "sanctions", "prosecution", "attachment", "attachments",
    "charge", "charges", "bail", "arrest", "arrested", "conviction",
    "convicted", "acquittal", "acquitted", "indictment", "indicted",
    "appeal", "appeals", "injunction", "warrant", "warrants", "plea",
    "custody", "summons", "notice", "forfeiture", "quashing",
})


def _has_term(text: str, terms: tuple[str, ...]) -> bool:
    """True when any term appears as a whole word (so 'unconfirmed' != 'confirmed')."""
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)


def _polarity(text: str) -> tuple[bool, bool]:
    """Return (has_negation, has_affirmation) for a piece of text."""
    return _has_term(text, _NEGATION_TERMS), _has_term(text, _AFFIRMATION_TERMS)


def _legal_objects(text: str) -> set[str]:
    """Procedural objects named by a piece of text."""
    words = set(re.findall(r"[a-z]+", text.lower()))
    return words & _LEGAL_OBJECTS


def _parallel_legal_developments(text_a: str, text_b: str) -> bool:
    """True when both texts describe legal stages but not the same one.

    "Sanction to prosecute quashed" and "ED's attachment upheld" are two
    different rulings in the same case. Flagging them as a contradiction
    would be a false alarm, so they are left out of the contradiction list
    (both findings still appear under their own lens).
    """
    objects_a = _legal_objects(text_a)
    objects_b = _legal_objects(text_b)
    if not objects_a or not objects_b:
        return False
    return not (objects_a & objects_b)


def _subjects(finding: dict[str, Any]) -> dict[str, int]:
    """Capitalised candidate subjects named by a finding, with their position."""
    text = f"{finding.get('title', '')} {finding.get('snippet', '')}"
    subjects: dict[str, int] = {}
    for match in _SUBJECT_RE.finditer(text):
        token = match.group(0)
        if token.lower() in _SUBJECT_STOPWORDS:
            continue
        subjects.setdefault(token, match.start())
    return subjects


def _detect_contradictions(lens_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect contradictions across the six investigative lenses.

    Two findings contradict each other when they carry opposite polarity
    ("denied" vs "confirmed") AND they are talking about the same subject.
    Requiring a shared subject is what stops two unrelated claims that
    happen to use opposite words from being reported as a contradiction.
    """
    contradictions: list[dict[str, Any]] = []
    lens_names = sorted(lens_results)

    for index, lens_a in enumerate(lens_names):
        for lens_b in lens_names[index + 1:]:
            for fa in lens_results[lens_a].get("findings", []):
                for fb in lens_results[lens_b].get("findings", []):
                    fa_text = f"{fa.get('title', '')} {fa.get('snippet', '')}".lower()
                    fb_text = f"{fb.get('title', '')} {fb.get('snippet', '')}".lower()
                    fa_neg, fa_aff = _polarity(fa_text)
                    fb_neg, fb_aff = _polarity(fb_text)

                    if not ((fa_neg and fb_aff) or (fa_aff and fb_neg)):
                        continue

                    if _parallel_legal_developments(fa_text, fb_text):
                        continue

                    subjects_a = _subjects(fa)
                    subjects_b = _subjects(fb)
                    shared = set(subjects_a) & set(subjects_b)
                    if not shared:
                        continue

                    # Prefer the longest shared token; on a tie prefer the one
                    # appearing later ("Chanda Kochhar" -> "Kochhar").
                    subject = max(
                        shared,
                        key=lambda token: (len(token), max(subjects_a[token], subjects_b[token])),
                    )
                    contradictions.append({
                        "lens_a": lens_a,
                        "lens_b": lens_b,
                        "finding_a": fa.get("title", "")[:80],
                        "finding_b": fb.get("title", "")[:80],
                        "subject": subject,
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


def investigate(question: str, api_key: str | None = None) -> dict[str, Any]:
    """Investigate a question using six lenses and return findings.

    Args:
        question: A plain-language question (e.g., "Why did the CEO resign?")
        api_key: Optional caller-supplied key for the synthesis call (BYOK).
            Falls back to the server's ``GROQ_API_KEY`` when omitted.

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

    # Run all six lenses concurrently — each lens is network-bound, so
    # serial execution would multiply the slowest source by six.
    lens_results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=len(_LENS_FUNCS)) as pool:
        futures = {
            lens_name: pool.submit(
                _run_lens, lens_name, entities, dates_amounts, question
            )
            for lens_name in _LENS_FUNCS
        }
        for lens_name, future in futures.items():
            lens_results[lens_name] = future.result()

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

    # Bounded LLM synthesis call (one Groq call when a key is available)
    synthesis = _synthesize(question, lens_results, contradictions, api_key=api_key)

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


def _synthesis_prompt(
    question: str,
    lens_results: dict[str, dict[str, Any]],
    contradictions: list[dict[str, Any]],
) -> str:
    """Build the compact evidence brief handed to the synthesis model."""
    lines = [f"QUESTION: {question}", "", "FINDINGS BY LENS:"]
    for lens_name in sorted(lens_results):
        findings = [
            f for f in lens_results[lens_name].get("findings", []) if f.get("url")
        ]
        if not findings:
            continue
        lines.append(f"\n[{lens_name}]")
        for finding in findings[:6]:
            date = finding.get("date") or "no date"
            lines.append(
                f"- ({date}) [{finding.get('tag', 'reported_unconfirmed')}] "
                f"{finding.get('title', '').strip()}"
            )
    if contradictions:
        lines.append("\nCONTRADICTIONS:")
        for c in contradictions[:8]:
            lines.append(
                f"- {c.get('subject', '?')}: {c.get('finding_a', '')} VS {c.get('finding_b', '')}"
            )
    lines.append(
        "\nWrite a CID-style briefing: what is established, what is only reported, "
        "what contradicts, and what is still unknown. Cite the bracketed dates. "
        "Do not invent facts or sources."
    )
    return "\n".join(lines)


def _groq_synthesis(
    question: str,
    lens_results: dict[str, dict[str, Any]],
    contradictions: list[dict[str, Any]],
    api_key: str | None = None,
) -> str | None:
    """One bounded Groq call. Returns None when no key/client is available.

    ``api_key`` is the key submitted by the caller (BYOK). It falls back to
    the server's ``GROQ_API_KEY`` so a self-hosted instance works with only
    an environment variable set.
    """
    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        return None
    try:
        from groq import Groq
    except ImportError:
        return None

    try:
        client = Groq(api_key=key)
        response = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL_LARGE", "openai/gpt-oss-120b"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a case officer briefing a investigator. Use only "
                        "the evidence provided. Mark each claim as established, "
                        "reported, or unknown."
                    ),
                },
                {"role": "user", "content": _synthesis_prompt(
                    question, lens_results, contradictions
                )},
            ],
            max_tokens=SYNTHESIS_MAX_TOKENS,
            temperature=0.2,
        )
        text = (response.choices[0].message.content or "").strip()
        return text or None
    except Exception:
        return None


def _synthesize(
    question: str,
    lens_results: dict[str, dict[str, Any]],
    contradictions: list[dict[str, Any]],
    api_key: str | None = None,
) -> str:
    """Bounded LLM synthesis call (~1-2k tokens total).

    Uses one Groq call when a key is available (the caller's key, else the
    server's ``GROQ_API_KEY``). Falls back to the mechanical summary when no
    key is configured or the call fails, so the endpoint always returns a
    non-empty synthesis.
    """
    if not _IN_TEST:
        try:
            llm_summary = _groq_synthesis(
                question, lens_results, contradictions, api_key=api_key
            )
            if llm_summary:
                return llm_summary
        except Exception:
            pass

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
