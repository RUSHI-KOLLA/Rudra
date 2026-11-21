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
import time
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any, Iterable

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

# Hard cap on the findings kept per lens. It bounds the response size and
# keeps the cross-lens contradiction scan (which compares every pair)
# affordable.
MAX_FINDINGS_PER_LENS = 40

# Wall-clock ceiling for one investigation when the caller sets none.
DEFAULT_DEADLINE_SECONDS = 60

# Test mode detection - the LLM synthesis path must stay off during tests
_IN_TEST = "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") is not None

# Valid provenance tags
VALID_TAGS = {"documented", "reported_unconfirmed", "inferred", "speculative"}


# ---------------------------------------------------------------------------
# Mechanical entity extraction from a question
# ---------------------------------------------------------------------------

#: Function words, auxiliaries, interrogatives and news filler. These never
#: identify a subject on their own.
_STOP_WORDS = frozenset({
    # interrogatives and auxiliaries
    "why", "what", "when", "where", "who", "whom", "whose", "which", "how",
    "whether", "did", "do", "does", "done", "is", "are", "was", "were", "be",
    "been", "being", "am", "has", "have", "had", "having", "will", "would",
    "shall", "should", "can", "could", "may", "might", "must", "need",
    # function words
    "the", "and", "or", "but", "if", "then", "than", "so", "because", "as",
    "of", "in", "on", "at", "to", "for", "from", "by", "with", "without",
    "about", "after", "before", "during", "since", "until", "while",
    "between", "through", "over", "under", "again", "further", "once",
    "here", "there", "all", "any", "both", "each", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "too", "very", "just", "also", "now", "still", "yet", "ever", "never",
    # news and task filler
    "report", "reports", "reported", "reporting", "latest", "update",
    "updates", "breaking", "news", "please", "tell", "explain", "investigate",
    "investigation", "looking", "look", "find", "research", "happen",
    "happened", "happens",
    # months and weekdays
    "january", "february", "march", "april", "june", "july", "august",
    "september", "october", "november", "december",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday",
    # pronouns
    "i", "me", "my", "we", "our", "you", "your", "he", "him", "his", "she",
    "her", "it", "its", "they", "them", "their", "this", "that", "these",
    "those",
})

#: Job titles and offices. A title is not a subject to investigate.
_ROLE_WORDS = frozenset({
    "ceo", "cfo", "coo", "cto", "cio", "cmo", "md", "chairman", "chairwoman",
    "chairperson", "founder", "cofounder", "president", "vicepresident",
    "minister", "secretary", "director", "directors", "governor",
    "commissioner", "judge", "justice", "magistrate", "officer", "partner",
    "analyst", "reporter", "lawyer", "prosecutor", "auditor", "inspector",
    "supervisor", "executive", "head", "chief", "sheriff", "mayor",
    "senator", "congressman", "administrator",
})

#: Words that can head an "X of Y" organisation name.
_ORG_HEAD_WORDS = frozenset({
    "bank", "ministry", "department", "university", "agency", "office",
    "court", "council", "committee", "institute", "commission", "board",
    "bureau", "authority", "fund", "house", "centre", "center", "group",
    "company", "corporation", "party", "school", "academy", "hospital",
    "museum", "library", "association", "federation", "union", "airline",
    "airlines", "motor", "motors", "steel", "securities", "capital",
    "partners", "associates", "technologies", "technology", "systems",
    "pharma", "energy", "power", "foods", "tribunal", "commission",
})

#: Name particles that always join the words around them.
_NAME_PARTICLES = frozenset({
    "de", "van", "von", "der", "den", "du", "da", "di", "del", "la", "le",
    "bin", "ibn", "al",
})

#: Words that only count as a subject when they are part of a longer name.
_GENERIC_ALONE = frozenset({
    "state", "government", "parliament", "senate", "congress", "court",
    "courts", "board", "ministry", "department", "agency", "commission",
    "council", "office", "bank", "banks", "company", "firm", "group",
    "market", "industry", "sector", "country", "city", "world", "people",
    "police", "army", "navy", "president", "prime", "minister", "party",
    "fraud", "corruption", "bribery", "money", "loan", "loans", "banking",
    "timeline", "history", "background", "context", "summary", "analysis",
    "resignation", "resigned", "allegations", "charges", "scandal",
    "investigation", "report", "reports", "truth", "facts", "evidence",
})


def _is_name_token(token: str) -> bool:
    """True when a token can be part of a name (person, company, acronym)."""
    if len(token) < 2 or not token[:1].isupper():
        return False
    lower = token.lower()
    return lower not in _STOP_WORDS and lower not in _ROLE_WORDS


def _extract_entities(question: str) -> list[str]:
    """Extract the subjects named in a question.

    Handles the forms people actually use: full names, single surnames,
    acronyms ("RBI"), one-word companies ("Boeing"), names carrying an
    organisation suffix ("State Bank", "ICICI Bank") and "of" style names
    ("Bank of Baroda").
    """
    tokens = re.findall(r"[A-Za-z][A-Za-z&]*", question)
    entities: list[str] = []

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not _is_name_token(token):
            index += 1
            continue

        phrase = [token]
        cursor = index + 1
        while cursor < len(tokens):
            following = tokens[cursor]
            if _is_name_token(following):
                phrase.append(following)
                cursor += 1
                continue
            lower = following.lower()
            if (
                lower in _NAME_PARTICLES
                and cursor + 1 < len(tokens)
                and _is_name_token(tokens[cursor + 1])
            ):
                phrase.append(following)
                cursor += 1
                continue
            if (
                lower == "of"
                and phrase[-1].lower() in _ORG_HEAD_WORDS
                and cursor + 1 < len(tokens)
                and _is_name_token(tokens[cursor + 1])
            ):
                phrase.append(following)
                cursor += 1
                continue
            break

        name = " ".join(phrase)
        # A lone generic word ("Bank", "Government") is not a subject.
        if len(phrase) > 1 or name.lower() not in _GENERIC_ALONE:
            if name not in entities:
                entities.append(name)
        index = cursor

    return entities[:5]  # Cap at 5 entities


def _fallback_subject(question: str) -> str:
    """A search subject for a question that names nobody.

    "Why did the CEO resign?" has no entity, but it still has content words
    worth searching; without this the six lenses would return nothing at all.
    """
    words: list[str] = []
    for token in re.findall(r"[A-Za-z][A-Za-z&]*", question):
        if token.lower() in _STOP_WORDS or len(token) < 3:
            continue
        words.append(token)
        if len(words) >= 4:
            break
    return " ".join(words)


def _search_subjects(question: str, entities: list[str]) -> list[str]:
    """What the lenses search for: the named subjects, or a fallback."""
    if entities:
        return entities
    fallback = _fallback_subject(question)
    return [fallback] if fallback else []


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


def _run_lens(lens_name: str, subjects: list[str], dates_amounts: dict[str, list[str]], question: str) -> dict[str, Any]:
    """Run one investigative lens against the subjects of the question.

    Returns {'queries': [...], 'findings': [...]} where each finding has
    {title, url, snippet, date, tag, lens, question}. Mechanical question
    extractions (entities/dates/amounts) live once in ``question_profile``
    instead of being repeated into every lens.

    The subjects are searched concurrently: each one is an independent set of
    network calls, so waiting for them in turn would multiply the slowest
    source by the number of subjects.

    A lens that raises is isolated: its error is recorded and the other
    lenses still report. One broken source must not void the investigation.
    """
    queries: list[str] = []
    findings: list[dict[str, Any]] = []
    seen_queries: set[str] = set()
    errors: list[str] = []

    search_fn = _LENS_FUNCS[lens_name]

    def search_subject(subject: str) -> list[dict[str, Any]]:
        try:
            return search_fn(subject)
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            return []

    if subjects:
        with ThreadPoolExecutor(max_workers=min(len(subjects), 3)) as pool:
            results_per_subject = list(pool.map(search_subject, subjects))
    else:
        results_per_subject = []

    for results in results_per_subject:
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

    findings = _cap_findings(findings)

    result: dict[str, Any] = {"queries": queries, "findings": findings}
    if errors:
        result["error"] = "; ".join(errors)
    return result


def _cap_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the response bounded without throwing away structured evidence.

    Web hits come first and can be numerous; structured records (Wikidata,
    EDGAR, GLEIF) are the most reliable facts, so they are kept even when
    the web hits fill the budget.
    """
    if len(findings) <= MAX_FINDINGS_PER_LENS:
        return findings
    structured = [f for f in findings if f.get("tag") == "inferred"]
    web = [f for f in findings if f.get("tag") != "inferred"]
    room = max(MAX_FINDINGS_PER_LENS - len(structured), 0)
    return web[:room] + structured[:MAX_FINDINGS_PER_LENS]


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
#: "unconfirmed" is deliberately absent: uncertainty is not the opposite of
#: confirmation, so an unconfirmed report does not contradict a confirmed one.
_NEGATION_TERMS = (
    "denied", "denies", "deny", "quashed", "rejected", "reversed", "cleared",
    "dismissed", "refuted", "false", "baseless", "unsubstantiated",
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


#: Mutually exclusive legal outcomes, as (one side, the other side) term
#: sets per axis. Two findings naming opposite sides of the same axis talk
#: about the same case, so they contradict — even when the procedural-object
#: guard would otherwise treat them as parallel stages.
_LEGAL_OUTCOME_AXES = (
    (
        frozenset({"convicted", "conviction", "sentenced", "found guilty"}),
        frozenset({"acquitted", "acquittal", "not guilty", "cleared of all charges"}),
    ),
)


def _has_term(text: str, terms: Iterable[str]) -> bool:
    """True when any term appears as a whole word (so 'unconfirmed' != 'confirmed')."""
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)


def _polarity(text: str) -> tuple[bool, bool]:
    """Return (has_negation, has_affirmation) for a piece of text."""
    return _has_term(text, _NEGATION_TERMS), _has_term(text, _AFFIRMATION_TERMS)


def _outcome_sides(text: str) -> set[tuple[int, str]]:
    """Which sides of which legal-outcome axes a text names.

    "Acquittal confirmed" and "Conviction denied" are mutually exclusive
    outcomes of one case. The procedural-object guard sees two different
    objects and would call them parallel stages, which would hide a real
    conflict.
    """
    sides: set[tuple[int, str]] = set()
    for index, (positive, negative) in enumerate(_LEGAL_OUTCOME_AXES):
        if _has_term(text, positive):
            sides.add((index, "positive"))
        if _has_term(text, negative):
            sides.add((index, "negative"))
    return sides


def _finding_signals(finding: dict[str, Any]) -> dict[str, Any]:
    """Precompute the signals used to compare one finding with another.

    The contradiction scan compares every finding with every other one, so
    the text is only scanned once per finding instead of once per pair.
    """
    text = f"{finding.get('title', '')} {finding.get('snippet', '')}".lower()
    negation, affirmation = _polarity(text)
    return {
        "text": text,
        "negation": negation,
        "affirmation": affirmation,
        "sides": _outcome_sides(text),
    }


def _exclusive_signals(signal_a: dict[str, Any], signal_b: dict[str, Any]) -> bool:
    """True when two findings name opposite sides of one legal outcome axis."""
    axes_a = {axis for axis, _ in signal_a["sides"]}
    axes_b = {axis for axis, _ in signal_b["sides"]}
    for axis in axes_a & axes_b:
        if (
            (axis, "positive") in signal_a["sides"]
            and (axis, "negative") in signal_b["sides"]
        ) or (
            (axis, "negative") in signal_a["sides"]
            and (axis, "positive") in signal_b["sides"]
        ):
            return True
    return False


def _signals_conflict(signal_a: dict[str, Any], signal_b: dict[str, Any]) -> bool:
    """True when two findings carry opposite signals.

    That is either opposite polarity ("denied" vs "confirmed") or opposite
    sides of one legal outcome axis (acquittal vs conviction).
    """
    if (signal_a["negation"] and signal_b["affirmation"]) or (
        signal_a["affirmation"] and signal_b["negation"]
    ):
        return True
    return _exclusive_signals(signal_a, signal_b)


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

    Two findings that name mutually exclusive legal outcomes (acquittal vs
    conviction) contradict even when both are phrased affirmatively.
    """
    contradictions: list[dict[str, Any]] = []
    lens_names = sorted(lens_results)

    # Every finding is scanned once; the pairwise comparison then works on
    # the precomputed signals.
    signals = {
        lens_name: [_finding_signals(f) for f in lens_results[lens_name].get("findings", [])]
        for lens_name in lens_names
    }

    for index, lens_a in enumerate(lens_names):
        for lens_b in lens_names[index + 1:]:
            for fa, signal_a in zip(
                lens_results[lens_a].get("findings", []), signals[lens_a]
            ):
                for fb, signal_b in zip(
                    lens_results[lens_b].get("findings", []), signals[lens_b]
                ):
                    exclusive = _exclusive_signals(signal_a, signal_b)
                    if not _signals_conflict(signal_a, signal_b):
                        continue

                    # Parallel legal developments are not a conflict — unless
                    # the two findings name mutually exclusive outcomes.
                    if not exclusive and _parallel_legal_developments(
                        signal_a["text"], signal_b["text"]
                    ):
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
    """Tag every finding with how many distinct lenses surfaced the same source.

    The same article often matches several lens queries. Counting the lenses
    that found it is a free strength signal: three lenses on one URL means
    the story is cross-cutting, not incidental.

    Duplicates inside a single lens are dropped first — one article listed
    twice by the same lens is one source, not two independent hits.
    """
    lenses_by_url: dict[str, set[str]] = {}

    for lens_name, data in lens_results.items():
        seen: set[str] = set()
        kept: list[dict[str, Any]] = []
        for finding in data.get("findings", []):
            url = finding.get("url")
            if url:
                if url in seen:
                    continue
                seen.add(url)
                lenses_by_url.setdefault(url, set()).add(lens_name)
            kept.append(finding)
        data["findings"] = kept

    for data in lens_results.values():
        for finding in data.get("findings", []):
            lenses = lenses_by_url.get(finding.get("url", ""), set())
            finding["corroboration"] = len(lenses) if lenses else 1


def investigate(
    question: str,
    api_key: str | None = None,
    deadline_seconds: float | None = None,
) -> dict[str, Any]:
    """Investigate a question using six lenses and return findings.

    Args:
        question: A plain-language question (e.g., "Why did the CEO resign?")
        api_key: Optional caller-supplied key for the synthesis call (BYOK).
            Falls back to the server's ``GROQ_API_KEY`` when omitted.
        deadline_seconds: Wall-clock budget for the whole investigation.
            When it passes, the lenses that are still running are abandoned
            and their partial results are returned.

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
    # A question that names nobody still has something to search for.
    subjects = _search_subjects(question, entities)

    budget = deadline_seconds if deadline_seconds is not None else DEFAULT_DEADLINE_SECONDS
    deadline = time.monotonic() + max(budget, 0.0)

    # Run all six lenses concurrently — each lens is network-bound, so
    # serial execution would multiply the slowest source by six.
    lens_results: dict[str, dict[str, Any]] = {}
    pool = ThreadPoolExecutor(max_workers=len(_LENS_FUNCS))
    try:
        futures = {
            lens_name: pool.submit(
                _run_lens, lens_name, subjects, dates_amounts, question
            )
            for lens_name in _LENS_FUNCS
        }
        # Wait for the whole fan-out, but never past the deadline: lenses
        # that finished keep their findings, the rest are reported as cut
        # short rather than holding the request open.
        done, _ = wait(
            futures.values(), timeout=max(deadline - time.monotonic(), 0.0)
        )
        for lens_name, future in futures.items():
            if future in done:
                lens_results[lens_name] = future.result()
            else:
                lens_results[lens_name] = {
                    "queries": [],
                    "findings": [],
                    "error": "investigation deadline exceeded",
                }
    finally:
        # Do not wait for the abandoned lenses — they keep their own provider
        # timeouts and die on their own.
        pool.shutdown(wait=False, cancel_futures=True)

    # Mark how many lenses surfaced each source
    _apply_corroboration(lens_results)

    # Detect contradictions across lenses
    contradictions = _detect_contradictions(lens_results)

    # Provenance totals count each source once. The per-lens view keeps the
    # breakdown, and each finding says how many lenses surfaced it.
    all_findings = [
        f for data in lens_results.values() for f in data.get("findings", [])
    ]
    canonical: dict[str, dict[str, Any]] = {}
    unlinked: list[dict[str, Any]] = []
    for f in all_findings:
        url = f.get("url")
        if url:
            canonical.setdefault(url, f)
        else:
            unlinked.append(f)
    unique_findings = list(canonical.values()) + unlinked

    tag_counts: dict[str, int] = {}
    for f in unique_findings:
        tag = f.get("tag", "speculative")
        tag_counts[tag] = tag_counts.get(tag, 0) + 1

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
            "total_findings": len(unique_findings),
            "unique_sources": len(canonical),
            "tag_counts": tag_counts,
            "lenses_run": list(_LENS_FUNCS.keys()),
            "lens_findings": len(all_findings),
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
