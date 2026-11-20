"""Tests for the new investigate(question) pipeline (v6 architecture).

Replaces run_match(paste) as the primary flow. Tests cover:
- schema.py v6: external_pressure field
- sources.py: free search/data sources
- investigation.py: investigate(question) with six lenses
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from vg.incidents.schema import (
    IncidentCard,
    SCHEMA_VERSION,
    WEIGHTS_VERSION,
    TEMPLATE_VERSION,
    load_card,
)
from vg.incidents.schema import Status, TriggerType, Tempo, ExitAuthority, Succession


# ---------------------------------------------------------------------------
# Task 1: schema.py v6 — external_pressure field
# ---------------------------------------------------------------------------


class TestSchemaV6ExternalPressure:
    """Test that external_pressure field exists on IncidentCard (v6)."""

    def test_versions_bumped_to_6(self):
        """All three versions bump to 6 when schema changes."""
        assert SCHEMA_VERSION == 6
        assert WEIGHTS_VERSION == 6
        assert TEMPLATE_VERSION == 6

    def test_card_has_external_pressure_field(self):
        """IncidentCard accepts and stores external_pressure."""
        card = IncidentCard(
            incident_id="test_1",
            title="Test",
            status=Status.CURATED,
            date="2024-01-01",
            recorded_at="2024-01-02",
            actors=["Alice", "Bob"],
            actor_roles=["ceo", "board"],
            sector="tech",
            geography="us",
            trigger="test",
            trigger_type=TriggerType.FRAUD,
            constraint_types=[],
            legal_outcome="none",
            escalation_vector=[],
            tempo=Tempo.DAYS,
            exit_authority=ExitAuthority.BOARD,
            succession=Succession.INTERNAL,
            timeline=[],
            resolution=[],
            external_pressure="regulatory investigation pending",
        )
        assert card.external_pressure == "regulatory investigation pending"

    def test_card_external_pressure_defaults_to_empty_string(self):
        """external_pressure defaults to empty string when not provided."""
        card = IncidentCard(
            incident_id="test_2",
            title="Test 2",
            status=Status.CURATED,
            date="2024-01-01",
            recorded_at="2024-01-02",
            actors=["Alice", "Bob"],
            actor_roles=["ceo", "board"],
            sector="tech",
            geography="us",
            trigger="test",
            trigger_type=TriggerType.FRAUD,
            constraint_types=[],
            legal_outcome="none",
            escalation_vector=[],
            tempo=Tempo.DAYS,
            exit_authority=ExitAuthority.BOARD,
            succession=Succession.INTERNAL,
            timeline=[],
            resolution=[],
        )
        assert card.external_pressure == ""

    def test_from_dict_handles_missing_external_pressure(self):
        """Loading a card without external_pressure (backward compat) defaults to empty."""
        data = {
            "incident_id": "test_3",
            "title": "Test 3",
            "status": "curated",
            "date": "2024-01-01",
            "recorded_at": "2024-01-02",
            "actors": ["Alice", "Bob"],
            "actor_roles": ["ceo", "board"],
            "sector": "tech",
            "geography": "us",
            "trigger": "test",
            "trigger_type": "fraud",
            "constraint_types": [],
            "legal_outcome": "none",
            "escalation_vector": [],
            "tempo": "days",
            "exit_authority": "board",
            "succession": "internal",
            "timeline": [],
            "resolution": [],
            # external_pressure deliberately absent
            "summary_embed": "",
            "claims": [],
            "sources": [],
        }
        card = IncidentCard.from_dict(data)
        assert card.external_pressure == ""


# ---------------------------------------------------------------------------
# Task 2: sources.py — free search/data sources
# ---------------------------------------------------------------------------


class TestSourcesFreeSearch:
    """Test sources.py: free search/data sources returning {title, url, snippet, date}."""

    def test_sources_module_exists(self):
        """sources.py module can be imported."""
        from vg.incidents import sources
        assert sources is not None

    def test_search_returns_list_of_dicts(self):
        """search_free returns a list of result dicts."""
        from vg.incidents.sources import search_free
        results = search_free("test query")
        assert isinstance(results, list)

    def test_result_dict_has_required_keys(self):
        """Each result dict has title, url, snippet, date keys."""
        from vg.incidents.sources import search_free
        results = search_free("test query")
        for r in results:
            assert set(r.keys()) >= {"title", "url", "snippet", "date"}, \
                f"Result missing keys: {r.keys()}"

    def test_six_lens_searches(self):
        """All six investigative lenses have search functions."""
        from vg.incidents.sources import (
            search_money, search_power, search_secrecy,
            search_timing, search_network, search_counter_case,
        )
        for fn in (search_money, search_power, search_secrecy,
                   search_timing, search_network, search_counter_case):
            results = fn("test entity")
            assert isinstance(results, list)

    def test_extract_dates_from_text(self):
        """Mechanical date extraction from text returns list of date strings."""
        from vg.incidents.sources import extract_dates
        text = "The event happened on 2024-01-15 and again on March 3, 2024."
        dates = extract_dates(text)
        assert "2024-01-15" in dates

    def test_extract_amounts_from_text(self):
        """Mechanical amount extraction from text returns list of amount strings."""
        from vg.incidents.sources import extract_amounts
        text = "The fine was $50 million and the settlement $100M."
        amounts = extract_amounts(text)
        assert len(amounts) >= 1

    def test_extract_names_from_text(self):
        """Mechanical name extraction (gazetteer) from text."""
        from vg.incidents.sources import extract_names
        text = "Chanda Kochhar and Sandeep Bakhshi were involved."
        names = extract_names(text)
        assert len(names) >= 1

    def test_no_tavily_dependency(self):
        """sources.py does not require Tavily API key for free sources."""
        import importlib
        import vg.incidents.sources as src
        importlib.reload(src)
        # Module imports without error even without Tavily key
        assert src is not None


# ---------------------------------------------------------------------------
# Task 3: investigation.py — investigate(question) pipeline
# ---------------------------------------------------------------------------


class TestInvestigatePipeline:
    """Test investigate(question) — question-driven mini CID investigator."""

    def test_investigate_function_exists(self):
        """investigate() function exists in investigation module."""
        from vg.incidents.investigation import investigate
        assert investigate is not None

    def test_investigate_returns_dict(self):
        """investigate returns a dict with investigation results."""
        from vg.incidents.investigation import investigate
        result = investigate("Why did the CEO resign?")
        assert isinstance(result, dict)

    def test_investigate_has_required_keys(self):
        """investigate result has question, lens_results, synthesis, provenance."""
        from vg.incidents.investigation import investigate
        result = investigate("Why did the CEO resign?")
        required = {"question", "lens_results", "synthesis", "provenance"}
        assert set(result.keys()) >= required, f"Missing keys: {set(result.keys()) ^ required}"

    def test_investigate_has_six_lenses(self):
        """lens_results contains all six investigative lenses."""
        from vg.incidents.investigation import investigate
        result = investigate("Why did the CEO resign?")
        lenses = set(result["lens_results"].keys())
        expected = {"money", "power", "secrecy", "timing", "network", "counter_case"}
        assert expected <= lenses, f"Missing lenses: {expected - lenses}"

    def test_investigate_each_lens_has_results(self):
        """Each lens result has queries and findings lists."""
        from vg.incidents.investigation import investigate
        result = investigate("Why did the CEO resign?")
        for lens_name, lens_data in result["lens_results"].items():
            assert "queries" in lens_data, f"{lens_name} missing 'queries'"
            assert "findings" in lens_data, f"{lens_name} missing 'findings'"
            assert isinstance(lens_data["queries"], list)
            assert isinstance(lens_data["findings"], list)

    def test_investigate_provenance_tags(self):
        """Every finding has a provenance tag (documented/reported_unconfirmed/inferred/speculative)."""
        from vg.incidents.investigation import investigate
        result = investigate("Why did the CEO resign?")
        valid_tags = {"documented", "reported_unconfirmed", "inferred", "speculative"}
        for lens_name, lens_data in result["lens_results"].items():
            for finding in lens_data["findings"]:
                assert "tag" in finding, f"{lens_name} finding missing 'tag'"
                assert finding["tag"] in valid_tags, \
                    f"{lens_name} finding has invalid tag: {finding['tag']}"

    def test_investigate_synthesis_is_string(self):
        """synthesis field is a string (one bounded LLM call output)."""
        from vg.incidents.investigation import investigate
        result = investigate("Why did the CEO resign?")
        assert isinstance(result["synthesis"], str)

    def test_investigate_contradictions_detected(self):
        """investigate identifies contradictions across lenses."""
        from vg.incidents.investigation import investigate
        result = investigate("Why did the CEO resign?")
        assert "contradictions" in result
        assert isinstance(result["contradictions"], list)


