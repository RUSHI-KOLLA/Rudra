# Mini CID / OpenCode Push — Review Evidence (2026-11-20)

## STATE (2026-11-20)

- Commit `16b7f1e` pushed to `origin/main`: investigate(question) pipeline v6
- 95 tests pass (75 original + 20 new), 0 failed, 0 skipped
- schema.py v6: SCHEMA/WEIGHTS/TEMPLATE_VERSION = 6, `external_pressure` field added
- sources.py: free search module, 6 lens functions, no Tavily dependency
- investigation.py: `investigate(question)` entry point, 6 lenses, contradiction detection
- Nvidia ranking unchanged: Kochhar 0.7407, Strauss-Kahn 0.7185, Easterbrook 0.6778
- Corpus: 22 artifact-backed, 2 paraphrase-backed (kalanick_uber_2017, strauss_kahn_imf_2011)

## NEXT (2026-11-20)

- Reviewer to audit the commit directly in this document
- Flag for review when ready
- Phase 5: decide on paraphrase cards (cut to 10 artifact-backed or mark unverified)

---

## REVIEW EVIDENCE (items 20-23)

### 20. Latest commit hash and git log

```
commit 16b7f1e — fix: investigate() — pass question to _run_lens (NameError bug)
commit 8b6998a — feat: investigate(question) pipeline v6 (mini CID investigator)
commit ef53b89 — fix: Phase 4 - claim extraction + regenerate evidence
```

### 21. git diff --stat

```
incidents/investigation.py           | 323 +++++++++++++++++++++++++++++++++++
incidents/schema.py                  |  11 +-
incidents/sources.py                 | 157 +++++++++++++++++
tests/test_incident_investigation.py | 260 ++++++++++++++++++++++++++++
4 files changed, 748 insertions(+), 3 deletions(-)
```

Key diffs:
- **schema.py**: `SCHEMA_VERSION`/`WEIGHTS_VERSION`/`TEMPLATE_VERSION` 5→6, added `external_pressure: str = ""` field
- **sources.py**: New — `search_free()`, 6 lens search functions, `extract_dates/amounts/names`, no Tavily dependency
- **investigation.py**: New — `investigate(question)`, `_extract_entities()`, `_run_lens()`, `_detect_contradictions()`, `_synthesize()`

### 22. Full pytest summary

```
============================================== 95 passed in 4.40s ==============================================
```

**95 passed, 0 failed, 0 skipped** — zero regressions.

### 23. Corpus provenance + real `investigate(question)` output

**Corpus provenance (24 cards):**
- **Artifact-backed: 22** — boeing_2019, commonwealth_games_2010, easterbrook_mcdonalds_2019, enron_2001, ftx_2022, ghosn_nissan_2018, hayward_bp_2010, kochhar_icici_2018, nirav_modi_pnb_2018, panama_papers_2016, park_geun_hye_2016, petraeus_cia_2012, rajat_gupta_2011, satyam_2009, theranos_2018, two_g_spectrum_2010, vijay_mallya_2016, volkswagen_2015, watergate_1972, wells_fargo_2016, wirecard_2020, yes_bank_2020
- **Paraphrase-backed: 2** — kalanick_uber_2017, strauss_kahn_imf_2011

**Real `investigate("Why did Chanda Kochhar resign from ICICI Bank in 2018?")`:**

| Field | Value |
|-------|-------|
| Lenses run | money, power, secrecy, timing, network, counter_case (all 6) |
| Total findings | 6 (1 per lens, from mechanical entity extraction) |
| Tag counts | `inferred: 6` (all from gazetteer/regex extraction — no source artifacts) |
| Contradictions | 0 |
| Synthesis | within 1500 token ceiling |
| Free search | empty (no API keys) — expected for free-source-only mode |

Every finding carries a provenance tag: `inferred` for mechanically extracted entities/dates/amounts, `reported_unconfirmed` for free-search snippets (secondhand), `documented` only with real source artifact + verbatim quote, `speculative` for forward-looking claims.

---

**The code is committed at `16b7f1e` on `origin/main`. Ready for review.**

**Stance engine: FROZEN. Phase 4 complete. Mini CID ready for review.**