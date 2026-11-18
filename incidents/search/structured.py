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


def search_structured(query: str) -> dict[str, Any]:
    """Structured web search.

    Args:
        query: Search query string

    Returns:
        Dict with 'results' (list of SearchResult) and optional 'error'.
        Gap metadata is attached by the caller (research.py) to keep
        the search layer decoupled from the question model.
    """
    if not config.tavily_api_key:
        return {
            "results": [],
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
            "error": f"Search failed: {e}"
        }

    results = []
    for item in data.get("results", [])[:5]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", "")[:300],
            "date": item.get("published_date", ""),
        })

    return {
        "results": results,
    }