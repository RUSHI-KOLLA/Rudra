"""Tests for the Mini CID investigator pipeline.

Covers:
- sources.py: free search/data sources (no paid APIs, no keys required)
- investigation.py: investigate(question) with six lenses, provenance,
  corroboration and contradiction detection
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


# ---------------------------------------------------------------------------
# sources.py — free search/data sources
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

    def test_extract_dates_returns_full_years(self):
        """Bare years come back whole (2018), not as the century prefix (20)."""
        from vg.incidents.sources import extract_dates
        dates = extract_dates("The event happened in 2018 and 2019 and 2020.")
        assert "2018" in dates
        assert "2019" in dates
        assert "2020" in dates
        assert "20" not in dates

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

    def test_incidents_package_has_no_store_dependency(self):
        """The package no longer exposes the Chroma-backed incident store."""
        import vg.incidents as pkg
        assert not hasattr(pkg, "rebuild_index")
        assert not hasattr(pkg, "load_all_cards")

    def test_project_does_not_require_embedding_dependencies(self):
        """chromadb / fastembed / onnxruntime are gone from the dependency set."""
        from pathlib import Path
        requirements = (
            Path(__file__).resolve().parents[1] / "requirements.txt"
        ).read_text().lower()
        for banned in ("chromadb", "fastembed", "onnxruntime", "tavily"):
            assert banned not in requirements, f"{banned} still required"


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

    def test_synthesis_without_key_is_mechanical(self, monkeypatch):
        """No LLM key -> the mechanical summary is used."""
        from vg.incidents import investigation as inv_mod
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        result = inv_mod.investigate("Why did the CEO resign?")
        assert result["synthesis"].startswith("Investigation of:")

    def test_synthesis_uses_llm_when_key_present(self, monkeypatch):
        """With a key and an available client, the LLM summary is returned."""
        from vg.incidents import investigation as inv_mod
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.setattr(inv_mod, "_IN_TEST", False)
        monkeypatch.setattr(
            inv_mod, "_groq_synthesis",
            lambda question, lens_results, contradictions, api_key=None: "LLM SUMMARY",
        )
        result = inv_mod.investigate("Why did the CEO resign?")
        assert result["synthesis"] == "LLM SUMMARY"

    def test_synthesis_uses_the_submitted_key(self, monkeypatch):
        """A key submitted by the caller is used for the synthesis call (BYOK)."""
        from vg.incidents import investigation as inv_mod

        seen: dict = {}

        def fake_groq(question, lens_results, contradictions, api_key=None):
            seen["api_key"] = api_key
            return "LLM SUMMARY"

        monkeypatch.setattr(inv_mod, "_IN_TEST", False)
        monkeypatch.setattr(inv_mod, "_groq_synthesis", fake_groq)

        inv_mod.investigate("Why did the CEO resign?", api_key="caller-key")
        assert seen["api_key"] == "caller-key"

    def test_synthesis_falls_back_when_llm_fails(self, monkeypatch):
        """A failing LLM call falls back to the mechanical summary."""
        from vg.incidents import investigation as inv_mod

        def boom(*args, **kwargs):
            raise RuntimeError("groq down")

        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.setattr(inv_mod, "_IN_TEST", False)
        monkeypatch.setattr(inv_mod, "_groq_synthesis", boom)
        result = inv_mod.investigate("Why did the CEO resign?")
        assert result["synthesis"].startswith("Investigation of:")

    def test_question_profile_holds_mechanical_extractions(self):
        """Entities/dates/amounts extracted from the question live in one profile."""
        from vg.incidents.investigation import investigate
        result = investigate("Why did Chanda Kochhar resign in 2018?")
        profile = result["question_profile"]
        assert "2018" in profile["dates"]
        assert profile["entities"]

    def test_mechanical_findings_are_not_repeated_per_lens(self):
        """Entity/date/amount findings are not duplicated into every lens."""
        from vg.incidents.investigation import investigate
        result = investigate("Why did Chanda Kochhar resign in 2018?")
        for lens, data in result["lens_results"].items():
            titles = [f["title"] for f in data["findings"]]
            assert not any(
                t.startswith(("Entity:", "Date:", "Amount:")) for t in titles
            ), f"{lens} still repeats mechanical findings"

    def test_finding_corroboration_counts_lenses(self, monkeypatch):
        """A finding surfaced by two lenses reports corroboration == 2."""
        from vg.incidents import investigation as inv_mod

        shared = {
            "title": "Chanda Kochhar case timeline report",
            "url": "https://example.com/shared",
            "snippet": "timeline of events",
            "date": "2018-06-18",
        }

        def mock_lens_search(entity):
            return [dict(shared)]

        mocks = {lens: mock_lens_search for lens in inv_mod._LENS_FUNCS.keys()}
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why did Chanda Kochhar resign?")
        money = result["lens_results"]["money"]["findings"]
        corroborated = [f for f in money if f.get("url") == "https://example.com/shared"]
        assert corroborated, "shared finding missing from money lens"
        assert corroborated[0]["corroboration"] == len(inv_mod._LENS_FUNCS)


    def test_corroboration_counts_distinct_lenses_not_occurrences(self, monkeypatch):
        """One URL seen twice by one lens and once by another is corroboration 2.

        Corroboration answers "how many lenses independently surfaced this
        source" — occurrences of the same URL inside one lens are not
        independent evidence.
        """
        from vg.incidents import investigation as inv_mod

        shared = {
            "title": "Chanda Kochhar case timeline report",
            "url": "https://example.com/shared",
            "snippet": "timeline of events",
            "date": "2018-06-18",
        }

        def mock_lens(entity):
            return [dict(shared), dict(shared)]

        mocks = {lens: mock_lens for lens in inv_mod._LENS_FUNCS}
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why did Chanda Kochhar resign?")
        money = result["lens_results"]["money"]["findings"]
        corroborated = [f for f in money if f.get("url") == "https://example.com/shared"]
        assert corroborated[0]["corroboration"] == len(inv_mod._LENS_FUNCS)

    def test_duplicate_findings_within_one_lens_are_deduped(self, monkeypatch):
        """The same article twice in one lens is one finding."""
        from vg.incidents import investigation as inv_mod

        shared = {
            "title": "Chanda Kochhar case timeline report",
            "url": "https://example.com/shared",
            "snippet": "timeline of events",
            "date": "2018-06-18",
        }

        def mock_lens(entity):
            return [dict(shared), dict(shared)]

        mocks = {lens: mock_lens for lens in inv_mod._LENS_FUNCS}
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why did Chanda Kochhar resign?")
        money = result["lens_results"]["money"]["findings"]
        assert len(money) == 1, money

    def test_totals_count_a_repeated_url_once(self, monkeypatch):
        """The same source must count once in the totals, not once per lens."""
        from vg.incidents import investigation as inv_mod

        shared = {
            "title": "Chanda Kochhar case timeline report",
            "url": "https://example.com/shared",
            "snippet": "timeline of events",
            "date": "2018-06-18",
        }

        def mock_lens(entity):
            return [dict(shared)]

        mocks = {lens: mock_lens for lens in inv_mod._LENS_FUNCS}
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why did Chanda Kochhar resign?")
        prov = result["provenance"]
        assert prov["total_findings"] == 1, prov
        assert prov["unique_sources"] == 1, prov
        assert prov["tag_counts"] == {"reported_unconfirmed": 1}, prov
        assert prov["lens_findings"] == len(inv_mod._LENS_FUNCS), prov


# ---------------------------------------------------------------------------
# Task 4: Mocked search_free() tests — provenance & contradiction detection
# ---------------------------------------------------------------------------


def _patch_lens_funcs(monkeypatch, mocks: dict):
    """Patch _LENS_FUNCS in investigation module directly (bypasses import-time cache)."""
    from vg.incidents import investigation as inv_mod
    for lens_name, mock_fn in mocks.items():
        monkeypatch.setitem(inv_mod._LENS_FUNCS, lens_name, mock_fn)


class TestInvestigateWithMockedSearch:
    """Test investigate() with mocked non-empty search_free() results."""

    def test_search_free_results_tagged_reported_unconfirmed(self, monkeypatch):
        """Snippets returned by search_free() are tagged reported_unconfirmed (never documented)."""
        from vg.incidents import investigation as inv_mod

        mock_results = [{
            "title": "Test Article",
            "url": "https://example.com/article",
            "snippet": "Test Entity was involved in financial fraud",
            "date": "2024-01-15",
            "query": "test entity payment contract funding"
        }]

        def mock_lens_search(entity):
            return mock_results

        mocks = {lens: mock_lens_search for lens in inv_mod._LENS_FUNCS.keys()}
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why did Test Entity CEO resign?")

        # Verify all search-derived findings have reported_unconfirmed tag
        for lens_name, lens_data in result["lens_results"].items():
            for finding in lens_data["findings"]:
                if finding.get("url"):  # This is a search result (not mechanical extraction)
                    assert finding["tag"] == "reported_unconfirmed", \
                        f"{lens_name} finding has tag {finding['tag']}, expected reported_unconfirmed"
                    # Explicitly verify it's NOT documented
                    assert finding["tag"] != "documented", \
                        f"{lens_name} search finding incorrectly tagged documented"

    def test_search_free_results_never_tagged_documented(self, monkeypatch):
        """Free search results are never tagged documented (requires real source artifact + verbatim quote)."""
        from vg.incidents import investigation as inv_mod

        mock_results = [{
            "title": "Another Article",
            "url": "https://example.com/another",
            "snippet": "Confirmed: Test Entity admitted to wrongdoing",
            "date": "2024-02-01",
            "query": "test entity"
        }]

        def mock_lens_search(entity):
            return mock_results

        mocks = {lens: mock_lens_search for lens in inv_mod._LENS_FUNCS.keys()}
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why did Test Entity resign?")

        # Even with "confirmed" language in snippet, free search = reported_unconfirmed
        for lens_name, lens_data in result["lens_results"].items():
            for finding in lens_data["findings"]:
                if finding.get("url"):
                    assert finding["tag"] == "reported_unconfirmed", \
                        f"Free search result must be reported_unconfirmed, got {finding['tag']}"

    def test_contradiction_detection_denial_vs_affirmation(self, monkeypatch):
        """_detect_contradictions() fires on denial vs affirmation across lenses."""
        from vg.incidents import investigation as inv_mod

        def mock_search_money(entity):
            return [{
                "title": "Money Report",
                "url": "https://example.com/money",
                "snippet": "Test Entity confirmed benefited from the deal",
                "date": "2024-01-15",
                "query": f"{entity} payment contract funding"
            }]

        def mock_search_secrecy(entity):
            return [{
                "title": "Secrecy Report",
                "url": "https://example.com/secrecy",
                "snippet": "Test Entity denied any benefit, claims unconfirmed",
                "date": "2024-01-16",
                "query": f"{entity} reported unconfirmed denied comment"
            }]

        def mock_empty(entity):
            return []

        mocks = {
            "money": mock_search_money,
            "secrecy": mock_search_secrecy,
            "power": mock_empty,
            "timing": mock_empty,
            "network": mock_empty,
            "counter_case": mock_empty,
        }
        _patch_lens_funcs(monkeypatch, mocks)

        # Use "Test Entity" (two capitalized words) so _extract_entities fallback matches it
        result = inv_mod.investigate("Why did Test Entity benefit?")

        # Should detect contradiction between money (affirmation) and secrecy (denial)
        assert len(result["contradictions"]) > 0, \
            f"Expected contradictions, got {result['contradictions']}"
        
        # Verify contradiction structure
        for c in result["contradictions"]:
            assert "lens_a" in c
            assert "lens_b" in c
            assert c["type"] == "denial_vs_affirmation"
            assert "finding_a" in c
            assert "finding_b" in c

    def test_contradiction_detection_no_false_positives(self, monkeypatch):
        """_detect_contradictions() doesn't fire when lenses agree."""
        from vg.incidents import investigation as inv_mod

        def mock_lens_search(entity):
            return [{
                "title": "Consistent Report",
                "url": "https://example.com/consistent",
                "snippet": "Test Entity confirmed involvement in the project",
                "date": "2024-01-15",
                "query": f"{entity} payment contract funding"
            }]

        mocks = {lens: mock_lens_search for lens in inv_mod._LENS_FUNCS.keys()}
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why was Test Entity involved?")
        assert result["contradictions"] == [], \
            f"Expected no contradictions, got {result['contradictions']}"

    def test_unconfirmed_is_not_treated_as_a_negation(self, monkeypatch):
        """"Unconfirmed" is uncertainty, not the opposite of "confirmed".

        The agreed contract keeps uncertainty out of the negation set: a
        report that nobody has confirmed does not deny a confirmed report.
        """
        from vg.incidents import investigation as inv_mod

        def mock_money(entity):
            return [{
                "title": "Kochhar payment confirmed by two sources",
                "url": "https://example.com/money",
                "snippet": "Kochhar payment confirmed by two sources",
                "date": "2024-01-15",
                "query": f"{entity} payment",
            }]

        def mock_secrecy(entity):
            return [{
                "title": "Kochhar payment remains unconfirmed",
                "url": "https://example.com/secrecy",
                "snippet": "Kochhar payment remains unconfirmed",
                "date": "2024-01-16",
                "query": f"{entity} unconfirmed",
            }]

        def mock_empty(entity):
            return []

        mocks = {
            "money": mock_money,
            "secrecy": mock_secrecy,
            "power": mock_empty,
            "timing": mock_empty,
            "network": mock_empty,
            "counter_case": mock_empty,
        }
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why did Chanda Kochhar resign?")
        assert result["contradictions"] == [], result["contradictions"]

    def test_mutually_exclusive_legal_outcomes_are_contradictions(self, monkeypatch):
        """Acquittal vs conviction is one case, two exclusive outcomes.

        The procedural-object guard treats "acquittal" and "conviction" as
        different objects (parallel stages). They are mutually exclusive
        outcomes, so this pair is a contradiction.
        """
        from vg.incidents import investigation as inv_mod

        def mock_money(entity):
            return [{
                "title": "Kochhar acquittal confirmed by the court",
                "url": "https://example.com/money",
                "snippet": "Kochhar acquittal confirmed by the court",
                "date": "2024-01-15",
                "query": f"{entity} payment",
            }]

        def mock_secrecy(entity):
            return [{
                "title": "Kochhar conviction denied by the court",
                "url": "https://example.com/secrecy",
                "snippet": "Kochhar conviction denied by the court",
                "date": "2024-01-16",
                "query": f"{entity} denied",
            }]

        def mock_empty(entity):
            return []

        mocks = {
            "money": mock_money,
            "secrecy": mock_secrecy,
            "power": mock_empty,
            "timing": mock_empty,
            "network": mock_empty,
            "counter_case": mock_empty,
        }
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why did Chanda Kochhar resign?")
        assert len(result["contradictions"]) == 1, result["contradictions"]
        contradiction = result["contradictions"][0]
        assert contradiction["type"] == "denial_vs_affirmation"
        assert contradiction["subject"] == "Kochhar"

    def test_two_affirmative_exclusive_outcomes_are_contradictions(self, monkeypatch):
        """"Acquitted" and "convicted" are opposites even without a denial word."""
        from vg.incidents import investigation as inv_mod

        def mock_money(entity):
            return [{
                "title": "Kochhar acquitted in the loan fraud case",
                "url": "https://example.com/money",
                "snippet": "Kochhar acquitted in the loan fraud case",
                "date": "2024-01-15",
                "query": f"{entity} payment",
            }]

        def mock_secrecy(entity):
            return [{
                "title": "Kochhar convicted in the loan fraud case",
                "url": "https://example.com/secrecy",
                "snippet": "Kochhar convicted in the loan fraud case",
                "date": "2024-01-16",
                "query": f"{entity} convicted",
            }]

        def mock_empty(entity):
            return []

        mocks = {
            "money": mock_money,
            "secrecy": mock_secrecy,
            "power": mock_empty,
            "timing": mock_empty,
            "network": mock_empty,
            "counter_case": mock_empty,
        }
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why did Chanda Kochhar resign?")
        assert len(result["contradictions"]) == 1, result["contradictions"]

    def test_parallel_legal_rulings_are_not_contradictions(self, monkeypatch):
        """Two different court rulings on the same case are not a contradiction.

        "Sanction to prosecute quashed" and "ED's attachment upheld" are two
        decisions about different questions in the same case — neither denies
        the other.
        """
        from vg.incidents import investigation as inv_mod

        def mock_money(entity):
            return [{
                "title": "Why tribunal upheld ED's attachment of Chanda Kochhar's "
                         "Mumbai flat in ICICI Bank loan fraud case",
                "url": "https://example.com/money",
                "snippet": "Why tribunal upheld ED's attachment of Chanda Kochhar's "
                           "Mumbai flat in ICICI Bank loan fraud case (ThePrint)",
                "date": "2019-01-10",
                "query": f"{entity} payment",
            }]

        def mock_secrecy(entity):
            return [{
                "title": "Sanction To Prosecute Chanda Kochhar Quashed By Bombay "
                         "High Court In Videocon Loan Case",
                "url": "https://example.com/secrecy",
                "snippet": "Sanction To Prosecute Chanda Kochhar Quashed By Bombay "
                           "High Court In Videocon Loan Case (LawChakra)",
                "date": "2019-01-11",
                "query": f"{entity} denied",
            }]

        def mock_empty(entity):
            return []

        mocks = {
            "money": mock_money,
            "secrecy": mock_secrecy,
            "power": mock_empty,
            "timing": mock_empty,
            "network": mock_empty,
            "counter_case": mock_empty,
        }
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why did Chanda Kochhar resign?")
        assert result["contradictions"] == [], \
            f"Expected no contradictions, got {result['contradictions']}"

    def test_same_legal_object_with_opposite_outcomes_is_a_contradiction(self, monkeypatch):
        """Bail denied vs bail approved IS a contradiction — same object, opposite outcome."""
        from vg.incidents import investigation as inv_mod

        def mock_money(entity):
            return [{
                "title": "Court denied bail for Kochhar",
                "url": "https://example.com/money",
                "snippet": "Court denied bail for Kochhar",
                "date": "2024-01-15",
                "query": f"{entity} payment",
            }]

        def mock_secrecy(entity):
            return [{
                "title": "Judge approved bail for Kochhar",
                "url": "https://example.com/secrecy",
                "snippet": "Judge approved bail for Kochhar",
                "date": "2024-01-16",
                "query": f"{entity} denied",
            }]

        def mock_empty(entity):
            return []

        mocks = {
            "money": mock_money,
            "secrecy": mock_secrecy,
            "power": mock_empty,
            "timing": mock_empty,
            "network": mock_empty,
            "counter_case": mock_empty,
        }
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why did Chanda Kochhar resign?")
        assert len(result["contradictions"]) == 1, \
            f"Expected one contradiction, got {result['contradictions']}"

    def test_contradiction_subject_skips_generic_capitalised_words(self, monkeypatch):
        """The reported subject is the person, not an interrogative or 'Court'."""
        from vg.incidents import investigation as inv_mod

        def mock_money(entity):
            return [{
                "title": "Why did Kochhar resign — Court denied the payment",
                "url": "https://example.com/money",
                "snippet": "Why did Kochhar resign — Court denied the payment",
                "date": "2024-01-15",
                "query": f"{entity} payment",
            }]

        def mock_secrecy(entity):
            return [{
                "title": "Kochhar confirmed the payment was approved",
                "url": "https://example.com/secrecy",
                "snippet": "Kochhar confirmed the payment was approved",
                "date": "2024-01-16",
                "query": f"{entity} denied",
            }]

        def mock_empty(entity):
            return []

        mocks = {
            "money": mock_money,
            "secrecy": mock_secrecy,
            "power": mock_empty,
            "timing": mock_empty,
            "network": mock_empty,
            "counter_case": mock_empty,
        }
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why did Chanda Kochhar resign?")
        assert result["contradictions"], "Expected a contradiction"
        assert result["contradictions"][0]["subject"] == "Kochhar"

    def test_non_http_source_urls_are_dropped(self, monkeypatch):
        """A source returning a javascript:/data: URL must not reach the client.

        The UI renders finding URLs as links, so the API boundary is where
        the scheme has to be checked.
        """
        from vg.incidents import investigation as inv_mod

        def mock_lens(entity):
            return [
                {
                    "title": "Hostile link",
                    "url": "javascript:alert(document.cookie)",
                    "snippet": "click me",
                    "date": "2024-01-15",
                    "query": f"{entity} query",
                },
                {
                    "title": "Legitimate link",
                    "url": "https://example.com/story",
                    "snippet": "safe",
                    "date": "2024-01-15",
                    "query": f"{entity} query",
                },
            ]

        mocks = {lens: mock_lens for lens in inv_mod._LENS_FUNCS}
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why did Chanda Kochhar resign?")
        urls = [f["url"] for f in result["lens_results"]["money"]["findings"]]
        assert urls == ["https://example.com/story"], urls

    def test_queries_are_listed_once_per_distinct_query(self, monkeypatch):
        """The 'queries' list holds the distinct queries run, not one per finding."""
        from vg.incidents import investigation as inv_mod

        def mock_lens(entity):
            return [
                {
                    "title": f"Finding {index}",
                    "url": f"https://example.com/{index}",
                    "snippet": "text",
                    "date": "2024-01-15",
                    "query": f'"{entity}" payment',
                }
                for index in range(3)
            ]

        mocks = {lens: mock_lens for lens in inv_mod._LENS_FUNCS}
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why did Chanda Kochhar resign?")
        queries = result["lens_results"]["money"]["queries"]
        assert queries == ['"Chanda Kochhar" payment'], queries
        assert len(result["lens_results"]["money"]["findings"]) == 3

    def test_wikidata_labels_are_fetched_in_one_batch(self, monkeypatch):
        """Entity labels are fetched in a single batched request, not one per claim.

        Fetching a label per claim means up to ~150 sequential HTTP requests
        for one entity — the request takes tens of seconds and hammers
        Wikidata's API.
        """
        import vg.incidents.sources as src

        claims = {
            f"P{index}": [{"mainsnak": {"datavalue": {"value": {"id": f"Q{index}"}}}}]
            for index in range(12)
        }
        entities = {
            f"Q{index}": {"labels": {"en": {"value": f"Label {index}"}}}
            for index in range(12)
        }
        entities["Q42"] = {"labels": {"en": {"value": "Subject"}}}

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"entities": entities}

        calls: list[str] = []

        def fake_get(url, **kwargs):
            calls.append(url)
            return FakeResponse()

        monkeypatch.setattr(src, "_IN_TEST", False)
        monkeypatch.setattr(src, "_wikidata_search_id", lambda entity: "Q42")
        monkeypatch.setattr(src, "_get_wikidata_claims", lambda entity_id: claims)
        monkeypatch.setattr(src.requests, "get", fake_get)

        results = src._search_wikidata("Subject")

        assert len(results) == 12
        assert len(calls) == 1, (
            f"expected 1 batched label request, got {len(calls)}: {calls}"
        )

    def test_lenses_run_concurrently(self, monkeypatch):
        """The six lenses run in parallel — a slow lens must not block the others."""
        import threading
        import time
        from vg.incidents import investigation as inv_mod

        lock = threading.Lock()
        state = {"active": 0, "max_active": 0}

        def mock_lens(entity):
            with lock:
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            time.sleep(0.3)
            with lock:
                state["active"] -= 1
            return []

        mocks = {lens: mock_lens for lens in inv_mod._LENS_FUNCS}
        _patch_lens_funcs(monkeypatch, mocks)

        inv_mod.investigate("Why did Chanda Kochhar resign?")
        assert state["max_active"] >= 2, (
            f"lenses ran sequentially (max concurrent = {state['max_active']})"
        )

    def test_one_failing_lens_does_not_break_the_investigation(self, monkeypatch):
        """A lens that raises is isolated; the other five still report findings."""
        from vg.incidents import investigation as inv_mod

        def mock_boom(entity):
            raise RuntimeError("source exploded")

        def mock_ok(entity):
            return [{
                "title": "Surviving lens finding",
                "url": "https://example.com/ok",
                "snippet": "still here",
                "date": "2024-01-15",
                "query": f"{entity} query",
            }]

        mocks = {lens: mock_ok for lens in inv_mod._LENS_FUNCS}
        mocks["money"] = mock_boom
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why did Chanda Kochhar resign?")
        assert result["lens_results"]["money"]["findings"] == []
        assert "error" in result["lens_results"]["money"]
        assert result["lens_results"]["power"]["findings"], "other lenses must survive"

    def test_detects_opposing_claims_about_same_subject(self, monkeypatch):
        """Opposing claims about the same subject across lenses are flagged."""
        from vg.incidents import investigation as inv_mod

        def mock_money(entity):
            return [{
                "title": "Kochhar confirmed the payment was approved",
                "url": "https://example.com/money",
                "snippet": "Kochhar confirmed the payment was approved",
                "date": "2024-01-15",
                "query": f"{entity} payment contract funding"
            }]

        def mock_secrecy(entity):
            return [{
                "title": "Kochhar denied approving the payment",
                "url": "https://example.com/secrecy",
                "snippet": "Kochhar denied approving the payment",
                "date": "2024-01-16",
                "query": f"{entity} reported unconfirmed denied comment"
            }]

        def mock_empty(entity):
            return []

        mocks = {
            "money": mock_money,
            "secrecy": mock_secrecy,
            "power": mock_empty,
            "timing": mock_empty,
            "network": mock_empty,
            "counter_case": mock_empty,
        }
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why did Chanda Kochhar approve the payment?")
        assert len(result["contradictions"]) > 0, \
            f"Expected contradictions, got {result['contradictions']}"

        contradiction = result["contradictions"][0]
        assert contradiction["type"] == "denial_vs_affirmation"
        assert contradiction["subject"]
        assert "kochhar" in contradiction["subject"].lower()

    def test_opposing_claims_about_different_subjects_are_not_flagged(self, monkeypatch):
        """Opposing wording about unrelated subjects is not a contradiction."""
        from vg.incidents import investigation as inv_mod

        def mock_money(entity):
            return [{
                "title": "Regulator confirmed the fine was approved",
                "url": "https://example.com/money",
                "snippet": "Regulator confirmed the fine was approved",
                "date": "2024-01-15",
                "query": f"{entity} payment"
            }]

        def mock_secrecy(entity):
            return [{
                "title": "Auditor denied approving the transfer",
                "url": "https://example.com/secrecy",
                "snippet": "Auditor denied approving the transfer",
                "date": "2024-01-16",
                "query": f"{entity} denied"
            }]

        def mock_empty(entity):
            return []

        mocks = {
            "money": mock_money,
            "secrecy": mock_secrecy,
            "power": mock_empty,
            "timing": mock_empty,
            "network": mock_empty,
            "counter_case": mock_empty,
        }
        _patch_lens_funcs(monkeypatch, mocks)

        result = inv_mod.investigate("Why was the payment approved?")
        assert result["contradictions"] == [], \
            f"Expected no contradictions, got {result['contradictions']}"


# ---------------------------------------------------------------------------
# Task 5: keyless news sources — Google News RSS + GDELT (Brave replacement)
# ---------------------------------------------------------------------------


class TestGoogleNewsParser:
    """_parse_google_news() turns a Google News RSS feed into result dicts."""

    RSS = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel>
      <item>
        <title>Bank chief quits over loan fraud - The Wire</title>
        <link>https://news.google.com/rss/articles/abc</link>
        <pubDate>Wed, 21 Mar 2018 10:00:00 GMT</pubDate>
        <description>&lt;a href="https://news.google.com/rss/articles/abc"&gt;Bank chief quits&lt;/a&gt;</description>
        <source url="https://thewire.in">The Wire</source>
      </item>
      <item>
        <title>Headline with no publisher suffix</title>
        <link>https://news.google.com/rss/articles/def</link>
        <pubDate>not a real date</pubDate>
        <source>Example News</source>
      </item>
    </channel></rss>"""

    def test_strips_publisher_suffix_from_title(self):
        from vg.incidents.sources import _parse_google_news
        results = _parse_google_news(self.RSS)
        assert results[0]["title"] == "Bank chief quits over loan fraud"

    def test_returns_url_date_and_tag(self):
        from vg.incidents.sources import _parse_google_news
        results = _parse_google_news(self.RSS)
        assert results[0]["url"] == "https://news.google.com/rss/articles/abc"
        assert results[0]["date"] == "2018-03-21"
        assert results[0]["tag"] == "reported_unconfirmed"
        assert "The Wire" in results[0]["snippet"]

    def test_survives_unparseable_date(self):
        from vg.incidents.sources import _parse_google_news
        results = _parse_google_news(self.RSS)
        assert results[1]["date"] == ""
        assert results[1]["title"] == "Headline with no publisher suffix"

    def test_empty_channel_returns_empty_list(self):
        from vg.incidents.sources import _parse_google_news
        assert _parse_google_news("<rss><channel></channel></rss>") == []

    def test_malformed_xml_returns_empty_list(self):
        from vg.incidents.sources import _parse_google_news
        assert _parse_google_news("<rss><channel>") == []


class TestGdeltParser:
    """_parse_gdelt() turns a GDELT DOC artlist payload into result dicts."""

    PAYLOAD = {
        "articles": [{
            "title": "ICICI Bank chief quits",
            "url": "https://example.com/a",
            "domain": "example.com",
            "seendate": "20180321T100000Z",
            "language": "English",
            "sourcecountry": "India",
        }, {
            "title": "",
            "url": "https://example.com/empty-title",
            "domain": "example.com",
            "seendate": "20180322T100000Z",
        }],
    }

    def test_parses_article_fields(self):
        from vg.incidents.sources import _parse_gdelt
        results = _parse_gdelt(self.PAYLOAD)
        assert len(results) == 1
        assert results[0]["title"] == "ICICI Bank chief quits"
        assert results[0]["url"] == "https://example.com/a"
        assert results[0]["date"] == "2018-03-21"
        assert results[0]["tag"] == "reported_unconfirmed"
        assert "example.com" in results[0]["snippet"]

    def test_empty_payload_returns_empty_list(self):
        from vg.incidents.sources import _parse_gdelt
        assert _parse_gdelt({}) == []


class TestKeylessSearchChain:
    """search_free() falls back Brave -> Google News -> GDELT without keys."""

    def test_uses_google_news_when_brave_returns_nothing(self, monkeypatch):
        from vg.incidents import sources as src
        monkeypatch.setattr(src, "_search_brave", lambda q: [])
        monkeypatch.setattr(src, "_search_google_news", lambda q: [
            {"title": "News hit", "url": "https://n.example/1", "snippet": "s", "date": "2018-03-21"}
        ])
        monkeypatch.setattr(src, "_search_gdelt", lambda q: [])
        results = src.search_free("test query")
        assert results[0]["title"] == "News hit"

    def test_falls_back_to_gdelt_when_news_empty(self, monkeypatch):
        from vg.incidents import sources as src
        monkeypatch.setattr(src, "_search_brave", lambda q: [])
        monkeypatch.setattr(src, "_search_google_news", lambda q: [])
        monkeypatch.setattr(src, "_search_gdelt", lambda q: [
            {"title": "GDELT hit", "url": "https://g.example/1", "snippet": "s", "date": "2018-03-21"}
        ])
        results = src.search_free("test query")
        assert results[0]["title"] == "GDELT hit"

    def test_gdelt_is_throttled_to_one_call_per_interval(self, monkeypatch):
        from vg.incidents import sources as src
        calls = []

        class _Response:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"articles": []}

        def fake_get(*args, **kwargs):
            calls.append(1)
            return _Response()

        monkeypatch.setattr(src, "_IN_TEST", False)
        monkeypatch.setattr(src.requests, "get", fake_get)
        monkeypatch.setattr(src, "_GDELT_LAST_CALL", 0.0)
        src._search_gdelt("first")
        src._search_gdelt("second")
        assert len(calls) == 1

    def test_lens_search_dedupes_results_by_url(self, monkeypatch):
        from vg.incidents import sources as src
        monkeypatch.setattr(src, "search_free", lambda q: [{
            "title": "Test Entity named in report", "url": "https://same.example/1",
            "snippet": "s", "date": "",
        }])
        results = src._lens_search("money", "Test Entity")
        assert [r["url"] for r in results] == ["https://same.example/1"]

    def test_lens_search_quotes_the_entity(self, monkeypatch):
        """Quoting the entity keeps Google News on-topic instead of fuzzy-matching noise."""
        from vg.incidents import sources as src
        seen_queries = []

        def fake_search(query):
            seen_queries.append(query)
            return []

        monkeypatch.setattr(src, "search_free", fake_search)
        src._lens_search("timing", "Chanda Kochhar")
        assert seen_queries, "expected at least one query"
        assert all('"Chanda Kochhar"' in q for q in seen_queries)

    def test_lens_search_drops_results_that_do_not_mention_the_entity(self, monkeypatch):
        from vg.incidents import sources as src
        monkeypatch.setattr(src, "search_free", lambda q: [
            {"title": "Changes on the cards for Australia Test team",
             "url": "https://noise.example/1", "snippet": "cricket", "date": ""},
            {"title": "Chanda Kochhar quits ICICI Bank",
             "url": "https://real.example/2", "snippet": "resignation", "date": ""},
        ])
        results = src._lens_search("timing", "Chanda Kochhar")
        assert [r["url"] for r in results] == ["https://real.example/2"]
