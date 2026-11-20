"""Free search/data sources for the investigate(question) pipeline.

Returns raw results only — gap metadata is attached by the caller.
All sources are free (no Tavily dependency). Each result dict has:
    {title, url, snippet, date}

Six investigative lenses, each producing search queries from a question:
    Money:    Who paid, who benefited, who lost? (filings, contracts, funding, EDGAR)
    Power:    Who appointed, who could remove, who protected? (board records, appointments, regulators)
    Secrecy:  What is reported but unconfirmed? Who won't comment? (press, denials, unnamed sources)
    Timing:   What changed in the weeks before? (dated news, event timelines)
    Network:  Who else is connected to these people or firms? (company registries, sanctions lists)
    Counter-case: What would have to be true for the official story to be whole? (adversarial queries)

Mechanical extraction helpers:
    extract_dates(text)   -> list[str]  (ISO dates and written dates)
    extract_amounts(text) -> list[str]  ($ amounts, millions/billions)
    extract_names(text)   -> list[str]  (capitalised person/entity names)
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Free search entry point
# ---------------------------------------------------------------------------

def search_free(query: str) -> list[dict[str, Any]]:
    """Free structured search returning raw results.

    No Tavily dependency — returns empty list when no free source is
    configured. The search layer is decoupled from the question model;
    gap/lens metadata is attached by the caller (investigation.py).
    """
    # Free sources: no API key required. Return empty list — the
    # investigation layer fills results from available free data.
    return []


# ---------------------------------------------------------------------------
# Six investigative lens search functions
# ---------------------------------------------------------------------------

LENS_QUERY_TEMPLATES = {
    "money": [
        "{entity} payment contract funding",
        "{entity} who benefited financially",
        "{entity} who lost money",
    ],
    "power": [
        "{entity} who appointed",
        "{entity} who could remove",
        "{entity} board appointment regulator",
    ],
    "secrecy": [
        "{entity} reported unconfirmed denied comment",
        "{entity} unnamed sources press",
        "{entity} who won't comment",
    ],
    "timing": [
        "{entity} weeks before changed",
        "{entity} dated event timeline",
        "{entity} what changed before",
    ],
    "network": [
        "{entity} connected people firm",
        "{entity} company registry sanctions",
        "{entity} associated entities",
    ],
    "counter_case": [
        "{entity} official story contradicted",
        "{entity} alternative explanation",
        "{entity} what would have to be true",
    ],
}


def search_money(entity: str) -> list[dict[str, Any]]:
    """Money lens: who paid, who benefited, who lost?"""
    return _lens_search("money", entity)


def search_power(entity: str) -> list[dict[str, Any]]:
    """Power lens: who appointed, who could remove, who protected?"""
    return _lens_search("power", entity)


def search_secrecy(entity: str) -> list[dict[str, Any]]:
    """Secrecy lens: what is reported but unconfirmed? who won't comment?"""
    return _lens_search("secrecy", entity)


def search_timing(entity: str) -> list[dict[str, Any]]:
    """Timing lens: what changed in the weeks before?"""
    return _lens_search("timing", entity)


def search_network(entity: str) -> list[dict[str, Any]]:
    """Network lens: who else is connected to these people or firms?"""
    return _lens_search("network", entity)


def search_counter_case(entity: str) -> list[dict[str, Any]]:
    """Counter-case lens: what would have to be true for the official story?"""
    return _lens_search("counter_case", entity)


def _lens_search(lens: str, entity: str) -> list[dict[str, Any]]:
    """Run a lens-specific search for an entity."""
    templates = LENS_QUERY_TEMPLATES.get(lens, [])
    results: list[dict[str, Any]] = []
    for template in templates:
        query = template.format(entity=entity)
        results.extend(search_free(query))
    return results


# ---------------------------------------------------------------------------
# Mechanical extraction helpers
# ---------------------------------------------------------------------------

_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_WRITTEN_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},\s+\d{4}\b",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(
    r"\$\s*\d+(?:\.\d+)?\s*(?:million|billion|M|B)?",
    re.IGNORECASE,
)
_NAME_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")


def extract_dates(text: str) -> list[str]:
    """Extract date strings from text (ISO and written formats)."""
    dates: list[str] = []
    dates.extend(_ISO_DATE_RE.findall(text))
    dates.extend(_WRITTEN_DATE_RE.findall(text))
    # Deduplicate while preserving order
    seen: set[str] = set()
    return [d for d in dates if not (d in seen or seen.add(d))]


def extract_amounts(text: str) -> list[str]:
    """Extract monetary amounts from text."""
    return _AMOUNT_RE.findall(text)


def extract_names(text: str) -> list[str]:
    """Extract capitalised person/entity names from text."""
    names = _NAME_RE.findall(text)
    seen: set[str] = set()
    return [n for n in names if not (n in seen or seen.add(n))]
