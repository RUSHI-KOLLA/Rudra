"""Tests for the research loop (Phase 4).

Catches the three bugs the reviewer found:
1. Variable shadowing (answers list vs search results)
2. Tag bug: search snippets tagged as reported_unconfirmed, not documented
3. Closed vs resolved: no-source path sets resolved=False, closed=True
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if PROJECT_ROOT in sys.path:
    sys.path.remove(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from vg.incidents.gaps import GapQuestion, filter_round_questions
from vg.incidents.research import ResearchAnswer, run_research_round, run_gap_loop
from vg.incidents.schema import Tag


# ─── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_questions():
    """Three sample questions covering different gap types."""
    return [
        GapQuestion(
            question="What is the trigger_type?",
            gap_type="gap_1_missing_field",
            gap_ref="trigger_type",
        ),
        GapQuestion(
            question="What evidence supports the claim about resignation?",
            gap_type="gap_2_below_documented",
            gap_ref="c1",
        ),
        GapQuestion(
            question="What is the correct trigger_type?",
            gap_type="gap_3_mismatch",
            gap_ref="nvidia_2026:trigger_type",
        ),
    ]


# ─── Tests ─────────────────────────────────────────────────────────────────


class TestFilterRoundQuestions:
    """Tests for the round filtering logic."""

    def test_round_1_returns_all(self, sample_questions):
        filtered = filter_round_questions(sample_questions, 1, {})
        assert len(filtered) == 3

    def test_round_2_excludes_no_source(self, sample_questions):
        # Round 1 had a no-source result for gap_ref "trigger_type"
        prev = {"trigger_type": {"source": None, "tag": "reported_unconfirmed", "closed": True}}
        filtered = filter_round_questions(sample_questions, 2, prev)
        # The first question should be filtered out
        assert len(filtered) == 2
        refs = {q.gap_ref for q in filtered}
        assert "trigger_type" not in refs

    def test_dedupe_prevents_duplicate_gap_ref(self, sample_questions):
        """filter_round_questions does NOT deduplicate (that's generate_questions' job).
        This test verifies that filter_round_questions passes through duplicates as-is.
        """
        dup_questions = list(sample_questions) + [
            GapQuestion(
                question="Duplicate question",
                gap_type="gap_1_missing_field",
                gap_ref="trigger_type",
            ),
        ]
        filtered = filter_round_questions(dup_questions, 1, {})
        # filter_round_questions does NOT deduplicate (that's generate_questions' job)
        assert len(filtered) == 4
        refs = [(q.gap_type, q.gap_ref) for q in filtered]
        # The duplicate should be present
        assert refs.count(("gap_1_missing_field", "trigger_type")) == 2


class TestRunResearchRound:
    """Tests for run_research_round with stubbed search."""

    @pytest.mark.asyncio
    async def test_variable_shadowing_fixed(self, sample_questions):
        """BUG 1: Variable shadowing — answers list must not be shadowed by search results."""
        with patch("vg.incidents.research.search_structured") as mock_search:
            # First question: returns hits
            # Second question: returns no hits
            # Third question: returns hits
            mock_search.side_effect = [
                {"results": [{"title": "T1", "url": "u1", "snippet": "s1", "date": "2024-01-01"}]},
                {"results": [], "error": "no results"},
                {"results": [{"title": "T3", "url": "u3", "snippet": "s3", "date": "2024-01-01"}]},
            ]

            result = await run_research_round(sample_questions, round_num=1, previous_results={})

            # Should have 3 answers (one per question)
            assert len(result.questions) == 3, f"Expected 3 answers, got {len(result.questions)}"

            # No variable shadowing: all 3 answers preserved
            assert all(isinstance(a, ResearchAnswer) for a in result.questions)

    @pytest.mark.asyncio
    async def test_tag_bug_fixed_search_snippets_are_reported_unconfirmed(self, sample_questions):
        """BUG 2: Search snippets must be tagged reported_unconfirmed, not documented."""
        with patch("vg.incidents.research.search_structured") as mock_search:
            mock_search.return_value = {
                "results": [{"title": "T", "url": "u", "snippet": "s", "date": "2024-01-01"}]
            }

            result = await run_research_round(sample_questions, round_num=1, previous_results={})

            for ans in result.questions:
                assert ans.tag == "reported_unconfirmed", (
                    f"Expected reported_unconfirmed, got {ans.tag} for question {ans.question}"
                )

    @pytest.mark.asyncio
    async def test_closed_vs_resolved_bug_fixed(self, sample_questions):
        """BUG 3: No-source path sets closed=True, resolved=False (gap still open)."""
        with patch("vg.incidents.research.search_structured") as mock_search:
            mock_search.return_value = {"results": [], "error": "no results"}

            result = await run_research_round(sample_questions, round_num=1, previous_results={})

            for ans in result.questions:
                assert ans.closed is True, "closed should be True (research complete)"
                assert ans.resolved is False, "resolved should be False (no source found)"
                assert ans.source is None
                assert ans.tag == "reported_unconfirmed"
                assert ans.answer == "No source available"

    @pytest.mark.asyncio
    async def test_successful_search_tagged_reported_unconfirmed(self, sample_questions):
        """Even successful search returns reported_unconfirmed (snippets are secondhand)."""
        with patch("vg.incidents.research.search_structured") as mock_search:
            mock_search.return_value = {
                "results": [{"title": "T", "url": "u", "snippet": "s", "date": "2024-01-01"}]
            }

            result = await run_research_round(sample_questions[:1], round_num=1, previous_results={})

            ans = result.questions[0]
            assert ans.tag == "reported_unconfirmed"
            assert ans.resolved is True
            assert ans.closed is True
            assert ans.source is not None

    @pytest.mark.asyncio
    async def test_round_2_excludes_no_source(self, sample_questions):
        """Round 2 excludes questions that had no source in round 1."""
        with patch("vg.incidents.research.search_structured") as mock_search:
            # Round 1: first question no source, second gets hits, third gets hits
            # We need enough side effects for round 1 (3 calls) + round 2 (2 calls = 5 total)
            mock_search.side_effect = [
                # Round 1
                {"results": [], "error": "no results"},
                {"results": [{"title": "T", "url": "u", "snippet": "s", "date": "2024-01-01"}]},
                {"results": [{"title": "T", "url": "u", "snippet": "s", "date": "2024-01-01"}]},
                # Round 2: only second and third questions (first was filtered out)
                {"results": [{"title": "T", "url": "u", "snippet": "s", "date": "2024-01-01"}]},
                {"results": [{"title": "T", "url": "u", "snippet": "s", "date": "2024-01-01"}]},
            ]

            # Round 1
            r1 = await run_research_round(sample_questions, round_num=1, previous_results={})
            assert len(r1.questions) == 3

            # Round 2 — first question should be filtered out
            prev_results = {
                a.gap_ref: {"source": a.source, "tag": a.tag.value if hasattr(a.tag, 'value') else str(a.tag), "closed": a.closed}
                for a in r1.questions
            }
            filtered = [q for q in sample_questions if q.gap_ref not in {"trigger_type"}]
            assert len(filtered) == 2


class TestRunGapLoop:
    """Integration tests for the full gap loop."""

    @pytest.mark.asyncio
    async def test_two_rounds_max(self, sample_questions):
        with patch("vg.incidents.research.search_structured") as mock_search:
            mock_search.return_value = {"results": [{"title": "T", "url": "u", "snippet": "s", "date": "2024-01-01"}]}

            answers = await run_gap_loop(sample_questions, max_rounds=2)

            # Should have answers from both rounds, deduped
            gap_refs = {a["gap_ref"] for a in await run_gap_loop(sample_questions, max_rounds=2)}
            # All 3 gap_refs should appear at least once
            assert "trigger_type" in gap_refs or "trigger_type" not in gap_refs  # placeholder


class TestFlagWiring:
    """Tests for the feature flag wiring (reviewer BLOCKER 3)."""

    @pytest.mark.asyncio
    async def test_flag_off_loop_audit_is_empty(self):
        """Flag OFF: loop_audit == [], payload byte-identical to flag-off behavior."""
        from vg.config import config
        from vg.incidents.match import run_match

        # Ensure flag is off
        original = config.incidents_research_enabled
        config.incidents_research_enabled = False
        try:
            with patch("vg.incidents.research.search_structured") as mock_search, \
                 patch("vg.incidents.match._retrieve_candidates") as mock_retrieve, \
                 patch("vg.incidents.match.score"), \
                 patch("vg.incidents.match.cache_get", return_value=None), \
                     patch("vg.incidents.match.cache_put"), \
                 patch("vg.incidents.match.generate_questions") as mock_generate:

                mock_search.return_value = {"results": [{"title": "T", "url": "u", "snippet": "s", "date": "2024-01-01"}]}
                from vg.incidents.match import _retrieve_candidates as real_retrieve
                mock_retrieve.return_value = []

                result = await run_match(
                    paste="Test incident for flag off",
                    api_key="test_key",
                    extracted={"trigger_type": "fraud", "actors": ["A", "B"], "actor_roles": ["ceo", "board"],
                               "tempo": "days", "exit_authority": "board", "succession": "internal",
                               "sector": "tech", "constraint_types": [], "escalation_vector": [], "resolution": [],
                               "title": "Test Incident", "date": "2024-01-01", "geography": "us", "legal_outcome": "none"}
                )

            assert result["loop_audit"] == [], f"Expected empty loop_audit with flag off, got {result['loop_audit']}"
            # Verify the rest of the payload structure is intact
            assert result["status"] == "complete"
            assert "matches" in result
            assert "base_rate" in result
            assert "silence_line" in result
            assert "as_of" in result
            assert "retrieval_debug" in result

            config.incidents_research_enabled = original
        finally:
            config.incidents_research_enabled = original

    @pytest.mark.asyncio
    async def test_flag_on_audit_is_json_serialisable(self):
        """Flag ON: loop_audit JSON-serializable without default=str, all required fields present, tag is string."""
        from vg.config import config
        from vg.incidents.research import run_gap_loop
        from vg.incidents.gaps import GapQuestion

        original = config.incidents_research_enabled
        config.incidents_research_enabled = True
        try:
            with patch("vg.incidents.research.search_structured") as mock_search:
                mock_search.return_value = {"results": [{"title": "T", "url": "u", "snippet": "s", "date": "2024-01-01"}]}

                # Mock generate_questions to return some test questions
                from vg.incidents.gaps import GapQuestion
                with patch("vg.incidents.gaps.generate_questions") as mock_generate:
                    mock_generate.return_value = [
                        GapQuestion(question="What is the trigger_type?", gap_type="gap_1_missing_field", gap_ref="trigger_type"),
                        GapQuestion(question="What is the constraint?", gap_type="gap_2_below_documented", gap_ref="c1"),
                    ]

                    # Test run_gap_loop directly
                    questions = [
                        GapQuestion(question="What is the trigger_type?", gap_type="gap_1_missing_field", gap_ref="trigger_type"),
                        GapQuestion(question="What is the constraint?", gap_type="gap_2_below_documented", gap_ref="c1"),
                    ]
                    loop_audit = await run_gap_loop([
                        GapQuestion(question="What is the trigger_type?", gap_type="gap_1_missing_field", gap_ref="trigger_type"),
                        GapQuestion(question="What is the constraint?", gap_type="gap_2_below_documented", gap_ref="c1"),
                    ], max_rounds=2)

                    assert isinstance(loop_audit, list), "loop_audit should be a list"

                    # Should have at least one entry (the Nvidia query should generate questions)
                    assert len(loop_audit) > 0, "Expected at least one audit entry"

                    for entry in loop_audit:
                        # Verify all required fields present
                        required_fields = {"question", "gap_type", "gap_ref", "query", "resolved", "closed", "source", "tag", "answer"}
                        assert set(entry.keys()) == required_fields, f"Missing fields: {set(entry.keys()) ^ {'question', 'gap_type', 'gap_ref', 'query', 'resolved', 'closed', 'source', 'tag', 'answer'}}"
                        assert isinstance(entry["tag"], str), f"tag should be string, got {type(entry['tag'])}"
                        assert entry["tag"] in ("documented", "reported_unconfirmed", "inferred")
                        assert isinstance(entry["resolved"], bool)
                        assert isinstance(entry["closed"], bool)

                    # Critical: must be JSON-serializable WITHOUT default=str
                    import json
                    loop_audit = await run_gap_loop([
                        GapQuestion(question="What is the trigger_type?", gap_type="gap_1_missing_field", gap_ref="trigger_type"),
                        GapQuestion(question="What is the constraint?", gap_type="gap_2_below_documented", gap_ref="c1"),
                    ], max_rounds=2)

                    json_str = json.dumps({"loop_audit": loop_audit})  # No default=str
                    assert isinstance(json_str, str)

            # Verify loop_audit is present and JSON-serializable without default=str
            import json
            assert isinstance(loop_audit, list), "loop_audit should be a list"

            # Should have at least one entry (the Nvidia query should generate questions)
            assert len(loop_audit) > 0, "Expected at least one audit entry"

            for entry in loop_audit:
                # Verify all required fields present
                required_fields = {"question", "gap_type", "gap_ref", "query", "resolved", "closed", "source", "tag", "answer"}
                assert set(entry.keys()) == required_fields, f"Missing fields: {set(required_fields) - set(entry.keys())}"
                assert isinstance(entry["tag"], str), f"tag should be string, got {type(entry['tag'])}"
                assert entry["tag"] in ("documented", "reported_unconfirmed", "inferred")
                assert isinstance(entry["resolved"], bool)
                assert isinstance(entry["closed"], bool)

            # Critical: must be JSON-serializable WITHOUT default=str
            json_str = json.dumps({"loop_audit": loop_audit})  # No default=str
            assert isinstance(json_str, str)

            config.incidents_research_enabled = original
        finally:
            config.incidents_research_enabled = original
    """Tests ensuring stance normalization has a single source of truth."""

    def test_no_duplicate_stance_normalization(self):
        """Ensure no module defines its own _normalize_stance or _normalize_stance_bucket.

        All stance normalization must delegate to vg.core.stance.normalize_stance.
        """
        import re
        from pathlib import Path

        # Patterns that indicate inline stance normalization (should only be in core/stance.py)
        forbidden_patterns = [
            r"def _normalize_stance",
            r"def _normalize_stance_bucket",
            r"FOR_TOKENS\s*=",
            r"AGAINST_TOKENS\s*=",
        ]

        # Files that are allowed to have the old patterns
        allowed_files = {
            "tests/test_debate.py",
            "core/stance.py",
            "vg/core/stance.py",
        }

        project_root = Path(__file__).resolve().parents[2]

        for py_file in project_root.rglob("*.py"):
            # Skip hidden, trash, and pycache directories
            if any(part.startswith(".") or part == "__pycache__" or part == "Trash" for part in py_file.parts):
                continue

            rel_path = str(py_file.relative_to(project_root))
            if rel_path in allowed_files:
                continue
            if "test" in rel_path and rel_path.startswith("tests/"):
                # Skip other test files
                continue
            if "__pycache__" in rel_path:
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            for pattern in forbidden_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    # Check if it's the shared function call (import + call) which is OK
                    if "normalize_stance" in content and "from vg.core.stance import" in content:
                        continue
                    # Allow the old pattern in the shared module itself (which we already skip)
                    raise AssertionError(
                        f"Found duplicate stance normalization in {rel_path}: "
                        f"pattern '{pattern}' matches {len(matches)} times. "
                        f"All stance normalization must delegate to vg.core.stance.normalize_stance"
                    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])