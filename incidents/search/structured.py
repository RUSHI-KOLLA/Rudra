"""Structured search for the gap loop.

Returns raw results only — gap metadata is attached by the caller (research.py).
This keeps the search layer reusable and decoupled from the question model.
"""

from typing import Any
from dataclasses import dataclass
import requests
from vg.config import config


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    date: str


def search_structured(query: str, gap_type: str, gap_ref: str) -> dict[str, Any]:
    """Structured web search for a gap question.

    Args:
        query: Search query string
        gap_type: Type of gap (gap_1_missing_field, gap_2_below_documented,
                  gap_3_mismatch, gap_4_new_shape)
        gap_ref: Reference identifying the gap (field name, claim id,
                 match_id+component, or "new_shape")

    Returns:
        Dict with 'results' (list of SearchResult), 'gap_type', 'gap_ref'
    """
    if not config.tavily_api_key:
        return {
            "results": [],
            "gap_type": gap_type,
            "gap_ref": gap_ref,
            "error": "Tavily API key not configured"
        }

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": config.tavily_api_key,
                "query": query,
                "max_results": 5,
                "include_raw_content": False,
                "search_depth": "basic",
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return {
            "results": [],
            "gap_type": gap_type,
            "gap_ref": gap_ref,
            "error": f"Search failed: {e}"
        }

    results = []
    for item in data.get("results", [])[:5]:
        results.append(SearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("content", "")[:300],
            date=item.get("published_date", ""),
        ))

    return {
        "results": [r.__dict__ for r in results],
        "gap_type": gap_type,
        "gap_ref": gap_ref,
    }