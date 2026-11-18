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
from vg.core.stance import normalize_stance
from .schema import Tag


@dataclass
class ResearchAnswer:
    question: str
    gap_type: str
    gap_ref: str
    query: str
    resolved: bool  # True if the gap is resolved (answer found), False if still open
    closed: bool  # True if the research for this gap is complete (whether resolved or not)
    source: Optional[str]
    tag: Tag
    answer: str

    def to_audit_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict for the loop_audit response."""
        return {
            "question": self.question,
            "gap_type": self.gap_type,
            "gap_ref": self.gap_ref,
            "query": self.query,
            "resolved": self.resolved,
            "closed": self.closed,
            "source": self.source,
            "tag": self.tag.value if hasattr(self.tag, 'value') else str(self.tag),
            "answer": self.answer,
        }


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

    answers: list[ResearchAnswer] = []

    for q in filtered[:5]:  # Max 5 questions per round
        # Run search (gap metadata attached by caller, not search layer)
        search_result = search_structured(q.question)

        # Check if we got results
        hits = search_result.get("results", [])
        error = search_result.get("error")

        if not hits or error:
            # No source available — gap remains open (not resolved)
            answer = ResearchAnswer(
                question=q.question,
                gap_type=q.gap_type,
                gap_ref=q.gap_ref,
                query=q.question,
                closed=True,      # research for this gap is complete (no source found)
                resolved=False,   # gap is NOT resolved
                source=None,
                tag="reported_unconfirmed",
                answer="No source available",
            )
            answers.append(answer)
            continue

        # For now, use first result as answer (in real impl, would synthesize from multiple)
        # A search snippet is a secondhand summary — tag as reported_unconfirmed
        first = hits[0]
        source = f"{first['title']} ({first['url']})"
        answer_text = first['snippet']

        answer = ResearchAnswer(
            question=q.question,
            gap_type=q.gap_type,
            gap_ref=q.gap_ref,
            query=q.question,
            closed=True,        # research for this gap is complete
            resolved=True,      # gap IS resolved (we found a source)
            source=source,
            tag="reported_unconfirmed",  # search snippets are secondhand summaries
            answer=answer_text,
        )
        answers.append(answer)

    stopped = len(filtered) == 0
    return ResearchResult(questions=answers, round=round_num, stopped=stopped)


async def run_gap_loop(questions: list[Any], max_rounds: int = 2) -> list[dict[str, Any]]:
    """Run the full gap loop (max 2 rounds).

    Returns a list of JSON-serializable dicts (via to_audit_dict()) for the loop_audit field.
    """
    all_answers: list[dict[str, Any]] = []
    previous_results: dict[str, Any] = {}

    for round_num in range(1, max_rounds + 1):
        result = await run_research_round(questions, round_num=round_num, previous_results=previous_results)
        # Convert to audit dicts for the response
        audit_answers = [ans.to_audit_dict() for ans in result.questions]
        all_answers.extend(audit_answers)

        # Build previous_results for next round's filtering
        for ans in result.questions:
            previous_results[ans.gap_ref] = {
                "source": ans.source,
                "tag": ans.tag.value if hasattr(ans.tag, 'value') else str(ans.tag),
                "closed": ans.closed,
                "resolved": ans.resolved,
            }

        if result.stopped or len(result.questions) == 0:
            break

    return all_answers