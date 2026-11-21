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

import os
import re
import requests
import sys
import threading
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Any

# Test mode detection - skip slow network calls during tests
_IN_TEST = "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") is not None

# Simple in-memory cache for Wikidata lookups
_WIKIDATA_ID_CACHE: dict[str, str | None] = {}
_WIKIDATA_CLAIMS_CACHE: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Free search entry point — Brave (optional) + Google News + GDELT + DDGS
# ---------------------------------------------------------------------------

_BRAVE_KEY = os.getenv("BRAVE_API_KEY")
_BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

# Keyless news sources (no API key, no credit card)
_GOOGLE_NEWS_ENDPOINT = "https://news.google.com/rss/search"
_GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
_GDELT_MIN_INTERVAL = 5.0  # GDELT asks for at most one request every 5 seconds
_GDELT_LAST_CALL = 0.0
#: Guards the GDELT throttle so concurrent lenses cannot burst past the limit.
_GDELT_LOCK = threading.Lock()

_USER_AGENT = "VG-Investigator/1.0 (contact: rushi@example.com)"


def _parse_google_news(xml_text: str, limit: int = 10) -> list[dict[str, Any]]:
    """Parse a Google News RSS feed into result dicts (pure, no network)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    results: list[dict[str, Any]] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue

        source = (item.findtext("source") or "").strip()
        suffix = f" - {source}"
        if source and title.endswith(suffix):
            title = title[: -len(suffix)].strip()

        try:
            date = parsedate_to_datetime(item.findtext("pubDate") or "").date().isoformat()
        except (TypeError, ValueError):
            date = ""

        results.append({
            "title": title,
            "url": link,
            "snippet": f"{title} ({source})" if source else title,
            "date": date,
            "tag": "reported_unconfirmed",
        })
        if len(results) >= limit:
            break
    return results


def _parse_gdelt(payload: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    """Parse a GDELT DOC artlist payload into result dicts (pure, no network)."""
    results: list[dict[str, Any]] = []
    for article in payload.get("articles", []):
        title = (article.get("title") or "").strip()
        url = (article.get("url") or "").strip()
        if not title or not url:
            continue

        seen = article.get("seendate") or ""
        if len(seen) >= 8 and seen[:8].isdigit():
            date = f"{seen[0:4]}-{seen[4:6]}-{seen[6:8]}"
        else:
            date = ""

        meta = [article.get("domain", ""), article.get("sourcecountry", "")]
        snippet = " | ".join(part for part in meta if part) or title

        results.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "date": date,
            "tag": "reported_unconfirmed",
        })
        if len(results) >= limit:
            break
    return results


def _search_google_news(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Google News RSS — free, keyless, no card required."""
    if _IN_TEST:
        return []
    try:
        r = requests.get(
            _GOOGLE_NEWS_ENDPOINT,
            params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
        )
        r.raise_for_status()
        return _parse_google_news(r.text, limit)
    except Exception:
        return []


def _search_gdelt(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """GDELT DOC API — free, keyless. Throttled to one request every 5 seconds."""
    global _GDELT_LAST_CALL
    if _IN_TEST or os.getenv("ENABLE_GDELT", "1") == "0":
        return []
    # The lock makes the throttle safe when several lenses run concurrently:
    # exactly one caller gets the window, the rest fall through to the next
    # source instead of bursting GDELT.
    with _GDELT_LOCK:
        now = time.monotonic()
        if now - _GDELT_LAST_CALL < _GDELT_MIN_INTERVAL:
            return []
        _GDELT_LAST_CALL = now
    try:
        r = requests.get(
            _GDELT_ENDPOINT,
            params={
                "query": query,
                "mode": "artlist",
                "maxrecords": limit,
                "format": "json",
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
        )
        r.raise_for_status()
        return _parse_gdelt(r.json(), limit)
    except Exception:
        return []



def _search_brave(query: str) -> list[dict[str, Any]]:
    """Brave Search API — optional; $5 free credit/month (~1,000 requests)."""
    if _IN_TEST or not _BRAVE_KEY:
        return []
    try:
        r = requests.get(
            _BRAVE_ENDPOINT,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": _BRAVE_KEY,
            },
            params={"q": query, "count": 10, "freshness": "py"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("web", {}).get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", "")[:300],
                "date": item.get("age", ""),
            })
        return results
    except Exception:
        return []


def _search_ddgs(query: str) -> list[dict[str, Any]]:
    """DuckDuckGo HTML scrape — unlimited, no key (disabled due to reliability issues)."""
    # DDGS is unreliable (rate limits, timeouts) — disabled by default.
    # Enable by setting ENABLE_DDGS=1 if needed.
    if _IN_TEST or not os.getenv("ENABLE_DDGS"):
        return []
    # ... original implementation would go here if enabled
    return []


def _search_ddgs_direct(query: str) -> list[dict[str, Any]]:
    """Direct requests fallback for DuckDuckGo (no library dependency)."""
    # Disabled by default - enable with ENABLE_DDGS=1
    if _IN_TEST or not os.getenv("ENABLE_DDGS"):
        return []
    try:
        headers = {"User-Agent": "VG-Investigator/1.0 (contact: rushi@example.com)"}
        r = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=headers,
            timeout=5,
        )
        r.raise_for_status()
        from html.parser import HTMLParser

        class DDGParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.results = []
                self.in_result = False
                self.current = {}
                self.in_title = False
                self.in_snippet = False

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "a" and attrs.get("class") == "result__snippet":
                    self.in_snippet = True
                if tag == "a" and attrs.get("class") == "result__url":
                    self.in_url = True
                if tag == "h2" and attrs.get("class") == "result__title":
                    self.in_title = True
                    self.current = {"title": "", "url": "", "snippet": ""}

            def handle_endtag(self, tag):
                if tag == "h2" and self.in_title:
                    self.in_title = False
                if tag == "a" and self.in_snippet:
                    self.in_snippet = False
                if tag == "a" and self.in_url:
                    self.in_url = False

            def handle_data(self, data):
                if self.in_title and "title" in self.current:
                    self.current["title"] += data
                if self.in_snippet and "snippet" in self.current:
                    self.current["snippet"] += data
                if getattr(self, "in_url", False) and "url" in self.current:
                    self.current["url"] += data

        parser = DDGParser()
        parser.feed(r.text)
        results = []
        for item in parser.results[:10]:
            if item.get("title"):
                results.append({
                    "title": item.get("title", "")[:200],
                    "url": item.get("url", ""),
                    "snippet": item.get("snippet", "")[:300],
                    "date": "",
                })
        return results
    except Exception:
        return []


def search_free(query: str) -> list[dict[str, Any]]:
    """Free search returning raw results.

    Priority: Brave Search (if BRAVE_API_KEY is set) -> Google News RSS
    (keyless, no card) -> GDELT (keyless, throttled) -> DDGS (opt-in).
    """
    results = _search_brave(query)
    if results:
        return results
    results = _search_google_news(query)
    if results:
        return results
    results = _search_gdelt(query)
    if results:
        return results
    # DDGS fallback disabled by default - enable with ENABLE_DDGS=1
    if os.getenv("ENABLE_DDGS"):
        results = _search_ddgs(query)
        if results:
            return results
        return _search_ddgs_direct(query)
    return []


# ---------------------------------------------------------------------------
# Structured data sources (free, no keys)
# ---------------------------------------------------------------------------

_WIKIDATA_ENTITY_API = "https://www.wikidata.org/wiki/Special:EntityData"
_WIKIDATA_SEARCH_API = "https://www.wikidata.org/w/api.php"
_OPENSANCTIONS_ENDPOINT = "https://api.opensanctions.org/v1/entities"
_GLEIF_ENDPOINT = "https://api.gleif.org/api/v1/lei-records"
_EDGAR_SEARCH_ENDPOINT = "https://www.sec.gov/cgi-bin/browse-edgar"

# Key Wikidata property IDs we care about for CID lenses
# High-value properties for investigation (filtered from full set)
_WIKIDATA_HIGH_VALUE_PROPS = {
    "P31": "instance of",
    "P27": "country of citizenship",
    "P19": "place of birth",
    "P20": "place of death",
    "P131": "located in",
    "P17": "country",
    "P159": "headquarters location",
    "P571": "inception date",
    "P569": "date of birth",
    "P570": "date of death",
    "P355": "subsidiary",
    "P749": "parent organization",
    "P112": "founded by",
    "P169": "chief executive officer",
    "P1337": "chairperson",
    "P1436": "director",
    "P156": "followed by",
    "P155": "follows",
    "P463": "member of",
    "P127": "owned by",
    "P1830": "owner of",
    "P1056": "product or material",
    "P971": "partner in business",
    "P1366": "replaced by",
    "P1365": "replaces",
    "P2670": "sanctioned by",
    "P3601": "sanctions list entry",
    "P106": "occupation",
    "P108": "employer",
    "P452": "industry",
    "P1128": "employees",
    "P2139": "market cap",
    "P2140": "revenue",
    "P1081": "number of employees",
    "P2044": "operating income",
    "P2046": "net income",
    "P39": "position held",
    "P102": "member of political party",
    "P1416": "affiliation",
    "P1107": "convicted of",
    "P1399": "convicted of",
}

# Low-value properties to skip (metadata, not investigative)
_WIKIDATA_SKIP_PROPS = {
    "P21", "P373", "P18", "P646",   # sex, commons category, image, freebase ID
    "P2002", "P2003", "P3417",      # social media handles
    "P551", "P735", "P734",         # residence, given name, family name
    "P3368", "P1971", "P6640",      # identifiers
    "P1344", "P6424", "P1889",      # participation, affiliation, aliases
    "P793", "P69",                  # significant events, education
    "P166", "P1344",                # awards, participation
}


def _wikidata_search_id(entity: str) -> str | None:
    """Find Wikidata entity ID for a name (with caching)."""
    if entity in _WIKIDATA_ID_CACHE:
        return _WIKIDATA_ID_CACHE[entity]
    try:
        r = requests.get(
            _WIKIDATA_SEARCH_API,
            params={
                "action": "wbsearchentities",
                "search": entity,
                "language": "en",
                "format": "json",
                "limit": 1,
            },
            headers={"User-Agent": "VG-Investigator/1.0"},
            timeout=5,
        )
        r.raise_for_status()
        results = r.json().get("search", [])
        entity_id = results[0]["id"] if results else None
        _WIKIDATA_ID_CACHE[entity] = entity_id
        return entity_id
    except Exception:
        _WIKIDATA_ID_CACHE[entity] = None
        return None


def _get_wikidata_claims(entity_id: str) -> dict[str, Any]:
    """Fetch claims for a Wikidata entity ID (with caching)."""
    if entity_id in _WIKIDATA_CLAIMS_CACHE:
        return _WIKIDATA_CLAIMS_CACHE[entity_id]
    try:
        r = requests.get(
            f"{_WIKIDATA_ENTITY_API}/{entity_id}.json",
            headers={"User-Agent": "VG-Investigator/1.0"},
            timeout=5,
        )
        r.raise_for_status()
        entity = r.json().get("entities", {}).get(entity_id, {})
        claims = entity.get("claims", {})
        _WIKIDATA_CLAIMS_CACHE[entity_id] = claims
        return claims
    except Exception:
        _WIKIDATA_CLAIMS_CACHE[entity_id] = {}
        return {}


# Cache for target entity labels
_WIKIDATA_LABEL_CACHE: dict[str, str] = {}

#: Wikidata allows up to 50 entity IDs per wbgetentities request.
_WIKIDATA_LABEL_BATCH = 50


def _get_wikidata_labels(entity_ids: list[str]) -> dict[str, str]:
    """Fetch English labels for many Wikidata IDs in one batched request.

    Fetching a label per claim means up to ~150 sequential HTTP requests for
    a single entity — tens of seconds of wall time and needless load on
    Wikidata's API. Batching collapses that into one request per 50 IDs.
    """
    unique_ids = list(dict.fromkeys(i for i in entity_ids if i))
    missing = [i for i in unique_ids if i not in _WIKIDATA_LABEL_CACHE]

    for start in range(0, len(missing), _WIKIDATA_LABEL_BATCH):
        chunk = missing[start:start + _WIKIDATA_LABEL_BATCH]
        try:
            r = requests.get(
                _WIKIDATA_SEARCH_API,
                params={
                    "action": "wbgetentities",
                    "ids": "|".join(chunk),
                    "props": "labels",
                    "languages": "en",
                    "format": "json",
                },
                headers={"User-Agent": "VG-Investigator/1.0"},
                timeout=5,
            )
            r.raise_for_status()
            entities = r.json().get("entities", {})
            for entity_id, data in entities.items():
                label = data.get("labels", {}).get("en", {}).get("value", entity_id)
                _WIKIDATA_LABEL_CACHE[entity_id] = label
        except Exception:
            for entity_id in chunk:
                _WIKIDATA_LABEL_CACHE.setdefault(entity_id, entity_id)

    return {
        entity_id: _WIKIDATA_LABEL_CACHE.get(entity_id, entity_id)
        for entity_id in unique_ids
    }


def _search_wikidata(entity: str) -> list[dict[str, Any]]:
    """Wikidata Entity API — structured entity relations (officers, subsidiaries, owners)."""
    if _IN_TEST:
        return []
    entity_id = _wikidata_search_id(entity)
    if not entity_id:
        return []

    claims = _get_wikidata_claims(entity_id)
    if not claims:
        return []

    # Collect every referenced entity ID first so all labels can be fetched
    # in one batch instead of one request per claim.
    target_ids: list[str] = []
    for prop_id, claim_list in claims.items():
        if prop_id in _WIKIDATA_SKIP_PROPS:
            continue
        for claim in claim_list[:5]:  # Limit per property
            val = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
            if isinstance(val, dict) and "id" in val:
                target_ids.append(val["id"])

    labels = _get_wikidata_labels([entity_id] + target_ids)
    entity_label = labels.get(entity_id, entity_id)
    results = []

    for prop_id, claim_list in claims.items():
        # Skip low-value metadata properties
        if prop_id in _WIKIDATA_SKIP_PROPS:
            continue
        prop_label = _WIKIDATA_HIGH_VALUE_PROPS.get(prop_id, prop_id)
        for claim in claim_list[:5]:  # Limit per property
            mainsnak = claim.get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})
            if not datavalue:
                continue

            val = datavalue.get("value", {})
            value_label = ""
            value_url = f"https://www.wikidata.org/wiki/{entity_id}"

            if isinstance(val, dict):
                if "id" in val:  # Entity reference
                    target_id = val["id"]
                    value_label = labels.get(target_id, target_id)
                    value_url = f"https://www.wikidata.org/wiki/{target_id}"
                elif "time" in val:  # Date
                    value_label = val["time"].replace("+", "")
                elif "amount" in val:  # Quantity
                    value_label = val["amount"]
                else:
                    value_label = str(val)
            else:
                value_label = str(val)

            if value_label:
                results.append({
                    "title": f"{entity_label} — {prop_label}",
                    "url": value_url,
                    "snippet": f"{prop_label}: {value_label}",
                    "date": "",
                    "tag": "inferred",  # Structured data = inferred
                })

    return results


def _search_opensanctions(entity: str) -> list[dict[str, Any]]:
    """OpenSanctions — companies + sanctions + watchlists + PEPs (includes OpenCorporates data).
    
    Note: Requires API key (set OPENSANCTIONS_API_KEY env var). 
    Free tier available at https://opensanctions.org/
    """
    if _IN_TEST:
        return []
    api_key = os.getenv("OPENSANCTIONS_API_KEY")
    if not api_key:
        return []  # Skip silently if no key
    try:
        # Use the sanctions dataset (requires API key)
        r = requests.get(
            "https://api.opensanctions.org/search/sanctions",
            params={"q": entity, "limit": 10},
            headers={"Authorization": f"ApiKey {api_key}"},
            timeout=10,
        )
        if r.status_code == 401:
            return []  # Invalid key, skip silently
        r.raise_for_status()
        results = []
        for e in r.json().get("results", []):
            caption = e.get("caption", "")
            schema = e.get("schema", "")
            countries = ", ".join(e.get("countries", []))
            description = e.get("description", "")[:200]
            entity_id = e.get("id", "")
            results.append({
                "title": caption,
                "url": f"https://opensanctions.org/entities/{entity_id}/",
                "snippet": f"{schema} | {countries} | {description}",
                "date": e.get("last_seen", ""),
                "tag": "inferred",  # Structured registry data
            })
        return results
    except Exception:
        return []


def _search_gleif(entity: str) -> list[dict[str, Any]]:
    """GLEIF LEI — legal entity verification, registration info."""
    if _IN_TEST:
        return []
    try:
        # Use fulltext search for better matching
        r = requests.get(
            _GLEIF_ENDPOINT,
            params={"filter[fulltext]": entity, "page[size]": 10},
            headers={"Accept": "application/vnd.api+json"},
            timeout=10,
        )
        r.raise_for_status()
        results = []
        for rec in r.json().get("data", []):
            attrs = rec.get("attributes", {})
            entity_data = attrs.get("entity", {})
            # GLEIF uses camelCase: legalName, not legal_name
            legal_name = entity_data.get("legalName", {}).get("name", "")
            lei = attrs.get("lei", "")
            status = entity_data.get("status", "")
            reg_addr = entity_data.get("legalAddress", {})
            country = reg_addr.get("country", "")
            results.append({
                "title": f"{legal_name} (LEI: {lei})" if legal_name else f"LEI: {lei}",
                "url": f"https://search.gleif.org/#/record/{lei}",
                "snippet": f"Status: {status} | Country: {country} | LEI: {lei}",
                "date": attrs.get("registration", {}).get("initialRegistrationDate", ""),
                "tag": "inferred",  # Structured registry data
            })
        return results
    except Exception:
        return []


def _search_edgar(entity: str) -> list[dict[str, Any]]:
    """SEC EDGAR — US public company filings (8-K, 10-K, insider trades, etc.)."""
    if _IN_TEST:
        return []
    # SEC blocks automated requests without proper User-Agent
    headers = {
        "User-Agent": "VG-Investigator/1.0 (contact: rushi@example.com)",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        # Search for company by name - returns HTML, we parse minimally
        r = requests.get(
            _EDGAR_SEARCH_ENDPOINT,
            params={"company": entity, "owner": "include", "action": "getcompany"},
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()
        # Parse HTML for filing links (simplified)
        results = []
        from html.parser import HTMLParser

        class FilingParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.in_table = False
                self.in_row = False
                self.cells = []
                self.current_cell = []
                self.filings = []

            def handle_starttag(self, tag, attrs):
                if tag == "table":
                    attrs_dict = dict(attrs)
                    if attrs_dict.get("class", "").startswith("tableFile"):
                        self.in_table = True
                if self.in_table and tag == "tr":
                    self.in_row = True
                    self.cells = []
                if self.in_row and tag in ("td", "th"):
                    self.current_cell = []

            def handle_endtag(self, tag):
                if tag in ("td", "th") and self.in_row:
                    cell_text = "".join(self.current_cell).strip()
                    self.cells.append(cell_text)
                if tag == "tr" and self.in_row:
                    self.in_row = False
                    if len(self.cells) >= 5:
                        self.filings.append(self.cells)
                if tag == "table" and self.in_table:
                    self.in_table = False

            def handle_data(self, data):
                if self.in_row:
                    self.current_cell.append(data)

        parser = FilingParser()
        parser.feed(r.text)

        for filing in parser.filings[:10]:  # Limit to 10 most recent
            if len(filing) >= 5:
                filing_type = filing[0]
                date = filing[3]
                doc_link = filing[4] if len(filing) > 4 else ""
                results.append({
                    "title": f"{entity} — {filing_type} filing",
                    "url": f"https://www.sec.gov{doc_link}" if doc_link.startswith("/") else doc_link,
                    "snippet": f"{filing_type} filed on {date}",
                    "date": date,
                    "tag": "inferred",  # Official filing = documented/inferred
                })
        return results
    except Exception:
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
    results = _lens_search("money", entity)
    # Add structured sources for Money
    results.extend(_search_edgar(entity))
    return results


def search_power(entity: str) -> list[dict[str, Any]]:
    """Power lens: who appointed, who could remove, who protected?"""
    results = _lens_search("power", entity)
    # Add structured sources for Power
    results.extend(_search_wikidata(entity))
    results.extend(_search_edgar(entity))
    return results


def search_secrecy(entity: str) -> list[dict[str, Any]]:
    """Secrecy lens: what is reported but unconfirmed? who won't comment?"""
    return _lens_search("secrecy", entity)


def search_timing(entity: str) -> list[dict[str, Any]]:
    """Timing lens: what changed in the weeks before?"""
    return _lens_search("timing", entity)


def search_network(entity: str) -> list[dict[str, Any]]:
    """Network lens: who else is connected to these people or firms?"""
    results = _lens_search("network", entity)
    # Add structured sources for Network
    results.extend(_search_wikidata(entity))
    results.extend(_search_opensanctions(entity))
    results.extend(_search_gleif(entity))
    return results


def search_counter_case(entity: str) -> list[dict[str, Any]]:
    """Counter-case lens: what would have to be true for the official story?"""
    results = _lens_search("counter_case", entity)
    # Add structured sources for Counter-case
    results.extend(_search_wikidata(entity))
    return results


def _mentions_entity(result: dict[str, Any], entity: str) -> bool:
    """True when a search hit actually mentions the entity we searched for."""
    tokens = [t.lower() for t in re.split(r"\W+", entity) if len(t) > 3]
    if not tokens:
        return True
    text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
    return any(token in text for token in tokens)


def _lens_search(lens: str, entity: str) -> list[dict[str, Any]]:
    """Run a lens-specific search for an entity using free web search."""
    templates = LENS_QUERY_TEMPLATES.get(lens, [])
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    # Quote the entity so news search matches the name exactly instead of
    # fuzzy-matching every word in the lens template.
    quoted_entity = f'"{entity}"'
    for template in templates:
        query = template.format(entity=quoted_entity)
        for r in search_free(query):
            # Google News ignores some query terms; drop hits that never
            # mention the entity (e.g. unrelated cricket coverage).
            if not _mentions_entity(r, entity):
                continue
            # The same article often matches several lens queries — keep it once.
            key = r.get("url") or f"{r.get('title', '')}|{r.get('date', '')}"
            if key in seen:
                continue
            seen.add(key)
            r["query"] = query  # Attach query for provenance
            results.append(r)
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
_YEAR_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")  # 1900-2099, not part of longer number
_AMOUNT_RE = re.compile(
    r"\$\s*\d+(?:\.\d+)?\s*(?:million|billion|M|B)?",
    re.IGNORECASE,
)
_NAME_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")


def extract_dates(text: str) -> list[str]:
    """Extract date strings from text (ISO, written formats, and bare years)."""
    dates: list[str] = []
    dates.extend(_ISO_DATE_RE.findall(text))
    dates.extend(_WRITTEN_DATE_RE.findall(text))
    dates.extend(_YEAR_RE.findall(text))
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