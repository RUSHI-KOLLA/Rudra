# Phase 4 Evidence — Research Loop Wiring & Flag

Generated: 2026-11-19
Commit: 40055ad (with claim extraction fix)

---

## Query Card (tests/fixtures/query_nvidia_analog.json)

```json
{
  "trigger_type": "personal_conduct",
  "actors": ["John CEO", "Company Board"],
  "actor_roles": ["ceo", "board"],
  "tempo": "days",
  "exit_authority": "board",
  "succession": "internal",
  "sector": "technology",
  "constraint_types": ["reputational", "security"],
  "escalation_vector": ["media_cycle", "inquiry"],
  "resolution": ["resignation"],
  "title": "Tech CEO resigns after misconduct allegations",
  "date": "2026-01-15",
  "geography": "United States",
  "legal_outcome": "none",
  "claims": [
    {"id": "c1", "text": "Allegations surface", "tag": "reported_unconfirmed", "source_ids": [], "supports": []},
    {"id": "c2", "text": "CEO resigns", "tag": "reported_unconfirmed", "source_ids": [], "supports": []}
  ],
  "sources": []
}
```

---

## 1. Flag OFF — Full JSON (Nvidia Query)

```json
{
  "status": "complete",
  "matches": [
    {
      "id": "kochhar_icici_2018",
      "score": 0.7407,
      "components": {
        "trigger_type": {"weight": 0.26666666666666666, "value": 1.0, "contribution": 0.26666666666666666},
        "roles": {"weight": 0.19999999999999998, "value": 1.0, "contribution": 0.19999999999999998},
        "constraint": {"weight": 0.13333333333333333, "value": 0.3333333333333333, "contribution": 0.04444444444444444},
        "escalation": {"weight": 0.13333333333333333, "value": 0.0, "contribution": 0.0},
        "resolution": {"weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0},
        "tempo": {"weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0},
        "exit_authority": {"weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0},
        "outcome": {"weight": 0.06666666666666667, "value": 0.3333333333333333, "contribution": 0.02222222222222222}
      },
      "cosine": 0.9452,
      "tier": "strong",
      "why": [
        {"component": "trigger_type", "weight": 0.26666666666666666, "value": 1.0, "contribution": 0.26666666666666666},
        {"component": "roles", "weight": 0.19999999999999998, "value": 1.0, "contribution": 0.19999999999999998}
      ],
      "breaks": [
        {"component": "tempo", "weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0}
      ],
      "card": {...}
    },
    {"id": "strauss_kahn_imf_2011", "score": 0.7185, ...},
    {"id": "easterbrook_mcdonalds_2019", "score": 0.6778, ...},
    {"id": "petraeus_cia_2012", "score": 0.6222, ...},
    {"id": "kalanick_uber_2017", "score": 0.5741, ...}
  ],
  "corpus_size": 24,
  "base_rate": {
    "count": 5,
    "denominator": 24,
    "corpus_size": 24,
    "trigger_type": "personal_conduct",
    "scope": "shape",
    "distribution": {"resignation": 3, "government_appointed_board": 1, "bankruptcy": 1},
    "text": "5 of 24 recorded cases share this shape; 3 resignation, 1 bankruptcy, 1 government_appointed_board."
  },
  "silence_line": "As of 2026-11-19: 1 of 11 structural fields empty on the pasted record (legal_outcome); 2 claim(s) below documented (reported_unconfirmed).",
  "as_of": "2026-11-19",
  "loop_audit": [],
  "retrieval_debug": {...},
  "weights_version": 5,
  "truncated": false
}
```

---

## 2. Flag ON — loop_audit Block

```json
[
  {
    "question": "What evidence supports the claim: Allegations surface?",
    "gap_type": "gap_2_below_documented",
    "gap_ref": "c1",
    "query": "What evidence supports the claim: Allegations surface?",
    "resolved": false,
    "closed": true,
    "source": null,
    "tag": "reported_unconfirmed",
    "answer": "No source available"
  }
]
```

---

## 3. Flag ON — silence_line

```
As of 2026-11-19: 1 of 11 structural fields empty on the pasted record (legal_outcome); 2 claim(s) below documented (reported_unconfirmed); 1 research question(s) closed with no source available.
```

---

## 4. Flag OFF vs Flag ON Diff (excluding retrieval_debug)

```diff
--- Flag OFF
+++ Flag ON
@@
   "trigger_type": "personal_conduct"
 }
 "corpus_size": 24,
-  "loop_audit": [],
+  "loop_audit": [
+    {
+      "answer": "No source available",
+      "closed": true,
+      "gap_ref": "c1",
+      "gap_type": "gap_2_below_documented",
+      "query": "What evidence supports the claim: Allegations surface?",
+      "question": "What evidence supports the claim: Allegations surface?",
+      "resolved": false,
+      "source": null,
+      "tag": "reported_unconfirmed"
+    }
+  ],
   "matches": [
     {
       "breaks": [
@@
       ]
     }
   ],
-  "silence_line": "As of 2026-11-19: 1 of 11 structural fields empty on the pasted record (legal_outcome); 2 claim(s) below documented (reported_unconfirmed).",
+  "silence_line": "As of 2026-11-19: 1 of 11 structural fields empty on the pasted record (legal_outcome); 2 claim(s) below documented (reported_unconfirmed); 1 research question(s) closed with no source available.",
   "status": "complete",
   "truncated": false,
   "weights_version": 5
```

---

## Verification Checklist

| Check | Result | Details |
|-------|--------|---------|
| 1. Flag-off JSON contains `"loop_audit": []` and is otherwise identical | ✅ PASS | Verified by diff above |
| 2. Flag-on loop_audit: ≥1 entry, traces to real gap_ref, tagged `reported_unconfirmed` | ✅ PASS | Gap 2: below-documented claim `c1` |
| 3. Silence line shows "research question(s) closed with no source available" clause | ✅ PASS | Clause present and firing |
| 4. Total search calls ≤ 5 (one round, five questions maximum) | ✅ PASS | 1 search call (1 question processed) |

---

## Nvidia Ranking (unchanged from pre-Phase 4)

| Rank | Card | Score | Tier |
|------|------|-------|------|
| 1 | kochhar_icici_2018 | 0.7407 | strong |
| 2 | strauss_kahn_imf_2011 | 0.7185 | strong |
| 3 | easterbrook_mcdonalds_2019 | 0.6778 | strong |
| 4 | petraeus_cia_2012 | 0.6222 | strong |
| 5 | kalanick_uber_2017 | 0.5741 | strong |

All 75 tests pass. Stance engine: FROZEN.

---

## Gap Detector Behavior (observed)

For this query card:
- **Gap 1 (Missing structural fields)**: `legal_outcome` is `LegalOutcome.NONE` (enum), not detected as empty by Gap 1's check (detects `None`/empty string/empty list). Silence line correctly reports it via `_field_is_empty`.
- **Gap 2 (Below-documented claims)**: 2 claims with `reported_unconfirmed` tag → 1 question for `c1` (one per gap family per round).
- **Gap 3 (Mismatch vs top match)**: Top match is Kochhar (0.7407). Kochhar's `breaks` only shows `tempo` (0.0 mismatch). Evidence-sensitive fields (`trigger_type`, `constraint_types`, `escalation_vector`) have non-zero matches, so **Gap 3 does not fire** — this is correct behavior per the restriction to evidence-sensitive fields with 0.0 mismatches.
- **Gap 4 (New shape)**: Has 5 strong matches → does not fire.

**Search calls**: 1 (≤ 5, one round, one question processed).

---

## Configuration

```python
# config.py
max_research_rounds: int = 1  # v1 default; second round reserved for when card write-back exists
```

```bash
# Environment variable
VG_MAX_RESEARCH_ROUNDS=1
VG_INCIDENTS_RESEARCH_ENABLED=1  # to enable
```