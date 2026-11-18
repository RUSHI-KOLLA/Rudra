"""Research loop for the gap loop.

Runs up to 2 rounds of research, one search per question, tags answers,
writes audit entries. Deduplicates by (gap_type, gap_ref). A duplicate
question does NOT count against the two-round cap.
"""

from typing import Any
from dataclasses import dataclass
from typing import Optional
from datetime import date

from .gaps import GapQuestion, filter_round_questions
from .search.structured import search_structured
from .match import normalize_stance, _normalize_stance_bucket
from .schema import Tag


@dataclass
class ResearchAnswer:
    question: str
    gap_type: str
    gap_ref: str
    query: str
    closed: bool
    source: Optional[str]
    tag: Tag
    answer: str


@dataclass
class ResearchResult:
    questions: list[ResearchAnswer]
    round: int
    stopped: bool  # True if stopped because no more questions or no source available


def _tag_from_source(source: Optional[str]) -> Tag:
    """Determine claim tag from source availability."""
    if source is None:
        return Tag.REPORTED_UNCONFIRMED
    return Tag.DOCUMENTED


async def run_research_round(
    questions: list[Any],  # list of GapQuestion
    *,
    round_num: int,
    previous_results: dict[str, Any] | None = None,
) -> ResearchResult:
    """Run one round of research.

    Each question gets one search call. Answers are tagged and recorded in loop_audit.
    """
    from .gaps import filter_round_questions
    from .gaps import GapQuestion

    # Filter questions for this round (dedupe + no-source exclusion)
    filtered = filter_round_questions(questions, round_num, previous_results or {})

    if not filtered:
        return ResearchResult(questions=[], round=round_num, stopped=True)

    results: list[ResearchAnswer] = []

    for q in filtered[:5]:  # Max 5 questions per round
        # Run search (gap metadata attached by caller, not search layer)
        search_result = search_structured(q.question)

        # Check if we got results
        results = search_result.get("results", [])
        error = search_result.get("error")

        if not results or error:
            # No source available
            answer = ResearchAnswer(
                question=q.question,
                gap_type=q.gap_type,
                gap_ref=q.gap_ref,
                query=q.question,
                closed=True,
                source=None,
                tag="reported_unconfirmed",
                answer="No source available",
            )
            results.append(answer)
            continue

        # For now, use first result as answer (in real impl, would synthesize from multiple)
        first = results[0]
        source = f"{first['title']} ({first['url']})"
        answer_text = first['snippet']

        answer = ResearchAnswer(
            question=q.question,
            gap_type=q.gap_type,
            gap_ref=q.gap_ref,
            query=q.question,
            closed=True,
            source=source,
            tag="documented",
            answer=answer_text,
        )
        results.append(answer)

    stopped = len(filtered) == 0
    return ResearchResult(questions=results, round=round_num, stopped=stopped)


def run_gap_loop(questions: list[Any], max_rounds: int = 2) -> list[Any]:
    """Run the full gap loop (max 2 rounds).

    Returns all ResearchAnswer entries with loop_audit fields.
    """
    all_answers: list[Any] = []
    previous_results: dict[str, Any] = {}

    for round_num in range(1, max_rounds + 1):
        result = run_research_round(questions, round_num=round_num, previous_results=previous_results)
        all_answers.extend(result.questions)

        # Build previous_results for next round's filtering
        for ans in result.questions:
            previous_results[ans.gap_ref] = {
                "source": ans.source,
                "tag": ans.tag,
                "closed": ans.closed,
            }

        if result.stopped or len(result.questions) == 0:
            break

    return all_answers