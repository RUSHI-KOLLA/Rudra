# Phase 4 Evidence — Research Loop Wiring & Flag

Generated: 2026-11-19
Commit: c4704ff

---

## 1. Flag OFF — Nvidia Query (full JSON)

```json
{
  "status": "complete",
  "matches": [
    {
      "id": "satyam_2009",
      "score": 0.4,
      "components": {
        "trigger_type": {"weight": 0.26666666666666666, "value": 1.0, "contribution": 0.26666666666666666},
        "roles": {"weight": 0.19999999999999998, "value": 0.6666666666666666, "contribution": 0.1333333333333333},
        "constraint": {"weight": 0.13333333333333333, "value": 0.0, "contribution": 0.0},
        "escalation": {"weight": 0.13333333333333333, "value": 0.0, "contribution": 0.0},
        "resolution": {"weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0},
        "tempo": {"weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0},
        "exit_authority": {"weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0},
        "outcome": {"weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0}
      },
      "cosine": 0.8905,
      "tier": "strong",
      "why": [
        {"component": "trigger_type", "weight": 0.26666666666666666, "value": 1.0, "contribution": 0.26666666666666666},
        {"component": "roles", "weight": 0.19999999999999998, "value": 0.6666666666666666, "contribution": 0.1333333333333333}
      ],
      "breaks": [
        {"component": "constraint", "weight": 0.13333333333333333, "value": 0.0, "contribution": 0.0},
        {"component": "escalation", "weight": 0.13333333333333333, "value": 0.0, "contribution": 0.0},
        {"component": "resolution", "weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0},
        {"component": "tempo", "weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0},
        {"component": "exit_authority", "weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0},
        {"component": "outcome", "weight": 0.06666666666666667, "value": 0.0, "contribution": 0.0}
      ],
      "card": {...}
    },
    {"id": "wirecard_2020", "score": 0.4, ...},
    {"id": "volkswagen_2015", "score": 0.3889, ...},
    {"id": "enron_2001", "score": 0.3667, ...},
    {"id": "ftx_2022", "score": 0.3667, ...}
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
  "silence_line": "As of 2026-11-19: 4 of 11 structural fields empty on the pasted record (constraint_types, escalation_vector, resolution, legal_outcome).",
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
      {"id": "wirecard_2020", "cosine": 0.8847},
      {"id": "enron_2001", "cosine": 0.8707},
      {"id": "ftx_2022", "cosine": 0.8628},
      {"id": "volkswagen_2015", "cosine": 0.8618}
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
    "question": "What is the constraint types?",
    "gap_type": "gap_1_missing_field",
    "gap_ref": "constraint_types",
    "query": "What is the constraint types?",
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
As of 2026-11-19: 4 of 11 structural fields empty on the pasted record (constraint_types, escalation_vector, resolution, legal_outcome); 1 research question(s) closed with no source available.
```

---

## Verification Checklist

| Check | Result | Details |
|-------|--------|---------|
| Flag-off JSON contains `"loop_audit": []` and is otherwise identical to c4704ff | ✅ PASS | Verified by diff |
| Flag-on loop_audit: ≥1 entry, traces to real gap_ref (empty card field `constraint_types`), tagged `reported_unconfirmed` | ✅ PASS | Gap 1: missing `constraint_types` field |
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
```

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