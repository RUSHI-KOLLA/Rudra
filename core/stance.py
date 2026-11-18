"""Shared stance normalization for all debate/agent modules.

Single source of truth for mapping verbose stances to for/against/neutral buckets.
Fixes:
- "disagree" -> "against" (not "for" via "agree" substring)
- "cannot assess" -> "neutral" (not "against")
- "harm is likely" -> "against" (not "for" via "likely" substring)
- "no chance of success" -> "against" (not "for" via "success" substring)
- "no doubt it will succeed" -> "for" (FOR-phrase beats negation gate)

Order of evaluation (FROZEN — see reviewer note 2026-11-18; do not tune token lists):
1. FOR phrases with "no" that mean positive (no doubt, no question)
2. Explicit neutral phrases (cannot assess, insufficient, etc.)
3. Negation gate: whole-word negators (no, not, never, etc.) -> against
4. FOR tokens (stems with prefix matching for inflections)
5. AGAINST tokens (remaining)
If this misfires, replace with model classification call — do not tune token lists.
"""

import re


# Neutral/abstain phrases checked FIRST in the original text (before tokenization)
_NEUTRAL_PHRASES = (
    "abstain",
    "cannot assess",
    "insufficient",
    "unclear",
    "unknown",
    "uncertain",
    "need more",
    "cannot determine",
)

# FOR phrases that contain "no" but mean positive
_FOR_PHRASES = (
    "no doubt",
    "no question",
    "no question about",
)

# Negation tokens — if any appear as a WHOLE WORD token, the stance is AGAINST
# (checked after FOR-phrases so "no doubt" stays FOR, but "no chance" -> against)
# These are EXACT word matches, NOT prefixes, to avoid "notable", "north", etc.
# Includes contracted forms without apostrophes (tokenizer strips apostrophes)
_NEGATION_TOKENS = (
    "no",
    "not",
    "never",
    "neither",
    "without",
    "hardly",
    "none",
    "cannot",
    "cant",
    "don",
    "wont",
    "isnt",
    "arent",
    "wasnt",
    "didnt",
    "doesnt",
    "hasnt",
    "hadnt",
    "wouldnt",
    "couldnt",
    "shouldnt",
)

# FOR tokens (prefix matching on word tokens)
# All tokens are STEMS (base forms) so prefix matching catches inflections:
# "improve" matches "improve", "improves", "improving", "improved"
# "advance" matches "advance", "advances", "advancing", "advanced"
_FOR_TOKENS = (
    "yes",
    "support",
    "agree",
    "true",
    "success",
    "pass",
    "benefit",
    "likely",
    "probable",
    "possible",
    "advance",
    "improve",
    "favor",
    "favour",
)

# AGAINST tokens (prefix matching on word tokens)
# "no" removed: negation gate handles "no" as exact word match to avoid "notable", "north", "norms", "nominee"
_AGAINST_TOKENS = (
    "reject",
    "disagree",
    "false",
    "fail",
    "against",
    "harm",
    "unlikely",
    "improbable",
    "risky",
    "danger",
    "worsens",
    "oppose",
    "opposition",
)


def _tokenize(text: str) -> tuple[str, ...]:
    """Extract word-like tokens from text (lowercase, alnum only)."""
    return tuple(re.findall(r"\w+", text.lower()))


def _has_any_token(tokens: tuple[str, ...], token_set: tuple[str, ...]) -> bool:
    """Check if any token in `tokens` starts with any prefix in `token_set`."""
    for tok in tokens:
        for prefix in token_set:
            if tok.startswith(prefix):
                return True
    return False


def normalize_stance(stance: str) -> str:
    """Map verbose stance to "for" | "against" | "neutral".

    Logic:
    1. Check explicit FOR phrases that contain "no" but mean positive
    2. Check explicit neutral phrases FIRST (before any tokenization)
    3. Check AGAINST tokens that are substrings of FOR tokens FIRST
       (e.g., "disagree" contains "agree", "harm" appears in "harmful")
    4. Check FOR tokens
    5. Check remaining AGAINST tokens
    5. Default to "neutral"
    """
    if not stance:
        return "neutral"

    normalized = stance.lower().strip()

    # 1. FOR phrases that contain "no" but mean positive (checked first)
    for phrase in _FOR_PHRASES:
        if phrase in normalized:
            return "for"

    # 2. Explicit neutral phrases checked in original text
    for phrase in _NEUTRAL_PHRASES:
        if phrase in normalized:
            return "neutral"

    # Tokenize for word-boundary-ish prefix matching
    tokens = _tokenize(normalized)

    # 2. Specific AGAINST tokens that are substrings of FOR tokens
    # Check BEFORE FOR so "disagree" -> "against" not "for" via "agree"
    if _has_any_token(tokens, ("disagree",)):
        return "against"
    # "harm" is a prefix of "harmful" etc. and appears in AGAINST list
    if _has_any_token(tokens, ("harm",)):
        return "against"

    # NEGATION GATE: if any negation token appears as a WHOLE WORD, stance is AGAINST
    # (checked after FOR-phrases so "no doubt" -> FOR, but "no chance" -> against)
    # Uses exact word matching (not prefix) to avoid "notable", "north", "norms", "nominee", etc.
    if any(tok in _NEGATION_TOKENS for tok in tokens):
        return "against"

    # 3. FOR tokens (original FOR-first behavior preserved)
    if _has_any_token(tokens, _FOR_TOKENS):
        return "for"

    # 4. Remaining AGAINST tokens
    if _has_any_token(tokens, _AGAINST_TOKENS):
        return "against"

    return "neutral"


def _normalize_stance_bucket(stance: str) -> str:
    """Alias for backward compatibility with existing code."""
    return normalize_stance(stance)


if __name__ == "__main__":
    # Quick self-test
    test_cases = [
        ("Yes, it will succeed", "for"),
        ("Yes, likely", "for"),
        ("Support the outcome", "for"),
        ("Agree with the assessment", "for"),
        ("True, this is correct", "for"),
        ("Success is probable", "for"),
        ("Likely to pass", "for"),
        ("Benefits are clear", "for"),
        ("No, will fail", "against"),
        ("Against the proposal", "against"),
        ("I disagree with the assessment", "against"),
        ("This is unlikely to succeed", "against"),
        ("Harm is likely", "against"),
        ("Harm is expected", "against"),
        ("This worsens the situation", "against"),
        ("Uncertain about the outcome", "neutral"),
        ("Need more information", "neutral"),
        ("Cannot assess at this time", "neutral"),
        ("I disagree", "against"),
        ("Cannot assess", "neutral"),
        ("Harm is likely", "against"),
        ("No doubt it will succeed", "for"),
        # Negation gate — reviewer requirement: negation + positive word = against
        ("There is no chance of success", "against"),
        ("There is no chance of success at all", "against"),
        ("Not likely to succeed", "against"),
        # Inflection/stem pairs — reviewer requirement: stems stored, inflections match
        ("It improves growth", "for"),
        ("It will improve growth", "for"),
        ("This advances the plan", "for"),
        ("This will advance the plan", "for"),
        # Negation gate — reviewer requirement: negation + positive word = against
        ("There is no chance of success", "against"),
        ("There is no chance of success at all", "against"),
        ("Not likely to succeed", "against"),
        ("Without any benefit to farmers", "against"),
        ("Never a success", "against"),
        ("Notable growth in exports", "neutral"),
        ("The north region will benefit", "for"),
        ("Norms will improve", "for"),
        ("The nominee supports the bill", "for"),
        # Cannot/don't contraction forms
        ("Cannot succeed", "against"),
        ("Don't succeed", "against"),
    ]

    all_pass = True
    for text, expected in test_cases:
        result = normalize_stance(text)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_pass = False
        print(f"{status} {text!r:40s} -> {result:8s} (expected {expected})")

    print(f"\n{'All tests passed!' if all_pass else 'Some tests FAILED!'}")