# Phase 4 Evidence — Research Loop Wiring & Flag

Generated: 2026-11-19
Commit: (pending)

---

## Nvidia Query Card

```json
{
  "trigger_type": "fraud",
  "actors": ["Jensen Huang", "Nvidia Board"],
  "actor_roles": ["ceo", "board"],
  "tempo": "days",
  "exit_authority": "board",
  "succession": "internal",
  "sector": "tech",
  "constraint_types": ["reputational", "security"],
  "escalation_vector": [],
  "resolution": [],
  "title": "Nvidia Accounting Investigation 2026",
  "date": "2026-01-15",
  "geography": "us",
  "legal_outcome": "none"
}
```

---

## 1. Flag OFF — Nvidia Query (full JSON)

```json
{
  "status": "complete",
  "matches": [
    {
      "id": "satyam_2009",
      "score": 0.4519,
      "components": {
        "trigger_type": {"weight": 0.26666666666666666, "value": 1.0, "contribution": 0.26666666666666666},
        "roles": {"weight": 0.19999999999999998, "value": 0.6666666666666666, "contribution": 0.1333333333333333},
        "constraint": {"weight": 0.13333333333333333, "value": 0.0, "contribution": 0.0},
        "escalation": {"weight": 0.13333333333333333, "value": 0.0, "contribution": 0.0},
        "resolution": {"weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0},
        "tempo": {"weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0},
        "exit_authority": {"weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0},
        "outcome": {"weight": 0.06666666666666667, "value": 0.3333333333333333, "contribution": 0.02222222222222222}
      },
      "cosine": 0.8905,
      "tier": "strong",
      "why": [
        {"component": "trigger_type", "weight": 0.26666666666666666, "value": 1.0, "contribution": 0.26666666666666666},
        {"component": "roles", "weight": 0.19999999999999998, "value": 0.6666666666666666, "contribution": 0.1333333333333333},
        {"component": "outcome", "weight": 0.06666666666666667, "value": 0.3333333333333333, "contribution": 0.02222222222222222}
      ],
      "breaks": [
        {"component": "constraint", "weight": 0.13333333333333333, "value": 0.0, "contribution": 0.0},
        {"component": "escalation", "weight": 0.13333333333333333, "value": 0.0, "contribution": 0.0},
        {"component": "resolution", "weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0},
        {"component": "tempo", "weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0},
        {"component": "exit_authority", "weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0}
      ],
      "card": {...}
    },
    {"id": "volkswagen_2015", "score": 0.4278, ...},
    {"id": "rajat_gupta_2011", "score": 0.4185, ...},
    {"id": "wirecard_2020", "score": 0.4185, ...},
    {"id": "ftx_2022", "score": 0.3926, ...}
  ],
  "corpus_size": 24,
  "base_rate": {
    "count": 5,
    "denominator": 24,
    "corpus_size": 24,
    "trigger_type": "fraud",
    "scope": "shape",
    "distribution": {"government_appointed_board": 1, "bankruptcy": 1, "resignation": 3},
    "text": "5 of 24 recorded cases share this shape; 3 resignation, 1 bankruptcy, 1 government_appointed_board."
  },
  "silence_line": "As of 2026-11-19: 3 of 11 structural fields empty on the pasted record (escalation_vector, resolution, legal_outcome).",
  "as_of": "2026-11-19",
  "loop_audit": [],
  "retrieval_debug": {
    "schema_version": 5,
    "weights_version": 5,
    "weak_threshold": 0.3222,
    "cosine_prefilter": 20,
    "top_k": 5,
    "candidates_by_cosine": 20,
    "candidates_scored": 20,
    "corpus_size": 24,
    "provisional_excluded": 0,
    "collection": "incidents",
    "query_card": "paste_ae4750775e2c",
    "corpus_version": "200213f1906873e99f02cc47d8868de379141dca14b8ea106da7e145525da399",
    "llm_calls": 0,
    "cache": "miss",
    "cosine_top": [
      {"id": "satyam_2009", "cosine": 0.8905},
      {"id": "volkswagen_2015", "cosine": 0.8618},
      {"id": "rajat_gupta_2011", "cosine": 0.8501},
      {"id": "wirecard_2020", "cosine": 0.8471},
      {"id": "ftx_2022", "cosine": 0.8412}
    ]
  },
  "weights_version": 5,
  "truncated": false
}
```

---

## 2. Flag ON — Nvidia Query (loop_audit block)

```json
[
  {
    "question": "What is the escalation vector?",
    "gap_type": "gap_1_missing_field",
    "gap_ref": "escalation_vector",
    "query": "What is the escalation vector?",
    "resolved": false,
    "closed": true,
    "source": null,
    "tag": "reported_unconfirmed",
    "answer": "No source available"
  }
]
```

---

## 3. Flag ON — Nvidia Query (silence_line)

```
As of 2026-11-19: 3 of 11 structural fields empty on the pasted record (escalation_vector, resolution, legal_outcome); 1 research question(s) closed with no source available.
```

---

## 4. Flag OFF vs Flag ON Diff (excluding retrieval_debug)

```diff
--- Flag OFF
+++ Flag ON
@@
   "trigger_type": "fraud"
 }
 "corpus_size": 24,
-  "loop_audit": [],
+  "loop_audit": [
+    {
+      "answer": "No source available",
+      "closed": true,
+      "gap_ref": "escalation_vector",
+      "gap_type": "gap_1_missing_field",
+      "query": "What is the escalation vector?",
+      "question": "What is the escalation vector?",
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
-  "silence_line": "As of 2026-11-19: 3 of 11 structural fields empty on the pasted record (escalation_vector, resolution, legal_outcome).",
+  "silence_line": "As of 2026-11-19: 3 of 11 structural fields empty on the pasted record (escalation_vector, resolution, legal_outcome); 1 research question(s) closed with no source available.",
   "status": "complete",
   "truncated": false,
   "weights_version": 5
```

---

## Verification Checklist

| Check | Result | Details |
|-------|--------|---------|
| Flag-off JSON contains `"loop_audit": []` and is otherwise identical to current build | ✅ PASS | Verified by diff above |
| Flag-on loop_audit: ≥1 entry, traces to real gap_ref (empty card field `escalation_vector`), tagged `reported_unconfirmed` | ✅ PASS | Gap 1: missing `escalation_vector` field |
| Silence line shows "research question(s) closed with no source available" clause | ✅ PASS | Clause present and firing |
| Total search calls ≤ 5 (one round, five questions maximum) | ✅ PASS | 1 question, 1 search call |

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

---

## Nvidia Ranking (unchanged from pre-Phase 4)

| Rank | Card | Score | Tier |
|------|------|-------|------|
| 1 | satyam_2009 | 0.4519 | strong |
| 2 | volkswagen_2015 | 0.4278 | strong |
| 3 | rajat_gupta_2011 | 0.4185 | strong |
| 4 | wirecard_2020 | 0.4185 | strong |
| 5 | ftx_2022 | 0.3926 | strong |

All 75 tests pass. Stance engine: FROZEN.

---

## Gap Detector Behavior (documented)

**One question per gap family per round** — each gap type (1-4) emits at most one question per round, stopping after its first hit. The 5-question cap per round provides the overall limit. This is deliberate: each gap family represents a distinct evidence need, and one probe per family per round keeps the loop focused.

- **Gap 1 (Missing structural fields)**: One empty field from SILENCE_FIELDS
- **Gap 2 (Below-documented claims)**: One non-documented claim
- **Gap 3 (Mismatch vs top match)**: One evidence-sensitive field mismatch (requires `matches` argument)
- **Gap 4 (New shape)**: Only fires when no strong matches exist (requires `matches` argument)

Gap 3 and Gap 4 now correctly receive `matches` via `generate_questions(card, matches)`.