# Implementation Readiness Report — Stage 9 (Implementation Readiness Test)

**Target:** `/home/rushi/vg/docs/designs/incident-memory.md` — DetailedRange 626..1010 (Detailed Implementation Plan)
**Reviewers (direct dispatch):** `egm-codebase-details` = completed; `egm-style` = completed; `egm-implementation-readiness` = not run (no report returned after multiple dispatches — recorded per loop protocol, not counted as a reviewer with zero findings)
**Standard applied:** `resources/document_standards/implementation-readiness-standard.md`
**Preset:** Consolidated report with all review rubrics (uninterrupted full flow)
**Date:** 2026-11-18

## Round outcome (this stage)

- 🔴 Blockers: **0** — no finding invalidates the architecture itself
- 🟡 Majors: **9** (codebase-details 8, style 1)
- 🟢 Nits: **6** (codebase-details 3, style 3)
- Terminology, file numbers 10–34, phase order, and cut-list reconciliation all internally consistent per the style reviewer.

---

## Reviewer A: egm-codebase-details (repo-verified readiness)

Audit method: checked every cited file/API/import against the working tree (`api/server.py`, `main.py`, `api/index.py`, `rag/builder.py`, `Dockerfile`, `config.py`, `.env.example`, `QUICKSTART.md`, `README.md`, `api/static/app.js`, `api/static/index.html`, `core/upset_patterns.py`, `search/web.py`).

### 🟡 Major findings

**F-02 — No `data/incidents/` corpus exists; 30 curated cards must be hand-authored before scoring can be exercised.**
- Design: entries 13–14 (lines 731–744): `data/incidents/README.md` plus `data/incidents/*.json` × 30 curated cards (user-authored, not implementation), outcomes pre-filled, claims tagged with real source refs; Nvidia excluded as held-out demo #31.
- Repo: `data/` contains only `sample_data.py`. No `data/incidents/` directory, no corpus JSON files, no excerpt files — including `data/incidents/nvidia_2026/sources/nvidia_2026_sources.md` designated at design lines 53–73, which is not committed.
- Impact: until those 30 JSON files + excerpt files are authored (a curator task), Phase 1–2 test suites can only run against empty/fixture corpora, and the E2E smoke ("Nvidia demo only after the 30-card corpus exists", verification lines ~1003–1006) cannot be executed as specified.

**F-03 — `config.py` lacks all six new incident keys; paths must be absolute and package-root-anchored.**
- Design: entry 15 (lines 746–753): new keys `incidents_data_path`, `incidents_collection`, `incident_weak_threshold` (0.45), `debate_enabled` (false), `max_research_rounds` (2), `questions_per_round` (5), resolved to absolute paths anchored at the package root, never CWD-relative.
- Repo: `config.py:12–82` defines exactly the existing keys (groq/tavily/gemini API keys, model selection, rate limiting, generation, RAG, debate, search). None of the six incident keys exist. There is no package-root anchor helper; `chroma_db_path: str = "./chroma_db"` (line 42) is CWD-relative, contradicting the plan's own "never CWD-relative" rule.
- Impact: entry 15 is implementable today (add keys), but store/match cannot resolve `data/incidents` paths CWD-independently until it lands.

**F-04 — `api/server.py` `do_POST` has no dispatch table; incident routes `POST /api/incident-match` and `POST /api/incident-outcome` do not exist.**
- Design: entry 22 (lines 818–828): dispatch table `{"/api/analyze": …, "/api/incident-match": …, "/api/incident-outcome": …}`; incident routes reuse `X-API-Key` handling; typed failures (503 embedder down, `needs_manual_entry`, "no source available"); `/api/analyze` gated on `debate_enabled`.
- Repo: `api/server.py:83–87` hardcodes `if parsed.path != "/api/analyze":` → 404. No dispatch table, no incident routes, no `debate_enabled` gate, no `needs_manual_entry` or 503-with-reason typing.
- Impact: blocks Phase 3 entries 21–22 until implemented.

**F-05 — `main.py` is not stripped to the keep-list; no incidents auto-build in `run_web`; no `debate_enabled` check in `analyze_async`/`analyze`.**
- Design: entry 23 (lines 830–837): `run_web` startup gains incidents analogue of RAG auto-build (ensure `incidents` collection exists / rebuild from JSON before serving); `analyze_async`/`analyze` check `debate_enabled` before any coordinator construction. Entry 5 (lines 665–672): strip to keep-list `analyze_async`, `analyze`, `run_web`, `_consume_option`; remove `run_cli`, `print_report`, `byok_setup`, `--cli/--json/--basic` argv handling.
- Repo: `main.py:36–57` `analyze_async` unconditionally constructs a `DebateCoordinator` (lines 44–51) with no flag check. `run_web` (lines 221–238) has the RAG analog only (Chroma sqlite check); no incidents collection rebuild. `run_cli` (lines 170–219), `print_report` (lines 60–148), `byok_setup` (lines 151–154), and `--cli/--json/--basic` handling (lines 174–182, 243–246) all remain.
- Impact: blocks Phase 3 entry 23; post-edit regression check needed against `run.py`/Dockerfile CMD/Procfile (they import only `run_web`/`analyze_async`, so low risk, must still be tested).

**F-06 — `api/index.py` returns 404 for all non-`/api/analyze` paths; no clean 501 for incident routes.**
- Design: entry 24 (lines 839–843): both incident routes return a clean 501 (read-only filesystem vs `PersistentClient` + model cache).
- Repo: `api/index.py:54–57` `if self.path != "/api/analyze":` → 404. No 501 handling.
- Impact: blocks Phase 3 entry 24.

**F-07 — Web UI (`api/static/index.html`, `app.js`) posts only to `/api/analyze`; no incident overlay, mode selector, or extracted-fields review state.**
- Design: entries 25–26 (lines 845–863): mode selector (Incident | Debate), multiline paste box with 4,000-char truncation notice, full-height overlay replacing the 350px aside, extracted-fields review/edit state between extract and save, panel flow render (tiers, base rate, silence line, "as of" stamp, `tag · source`, dual timelines, closest-match outcome, research Q&A, one-click override, cache indicator).
- Repo: `api/static/app.js:392–426` submits `fetch("/api/analyze", {question, enhanced})` only. `api/static/index.html:251–263` `.app-side` is a fixed 350px panel. No mode selector, no paste box, no overlay, no `tag · source` rendering.
- Impact: blocks Phase 3 entries 25–26; this is the largest surface and least specified (no component contract given for the overlay).

**F-08 — `rag/builder.py` needs `build_incidents()` added to `build_all()`; docstring fix tracked separately at entry 8.**
- Design: entry 16 (lines 755–761): `build_incidents()` reads JSON corpus, embeds `summary_embed`, upserts into `incidents` cosine collection so the Docker image pre-bakes it.
- Repo: `rag/builder.py:39–98` `build_all()` only builds the five `PERSONALITY_COLLECTIONS`; no `build_incidents()`, no `incidents` collection. Docstring stale `veritas.rag.builder` confirmed at line 3 (matches entry 8).
- Impact: entry 16 is implementable today, but entry 16's parenthetical ("Also corrects the stale docstring") duplicates Step 0 entry 8 — see style finding (duplicate ownership). The builder stage can't pre-bake an empty corpus meaningfully until entry 14's corpus exists (F-02).

**F-09 — `Dockerfile` does not set `FASTEMBED_CACHE_PATH` or copy the ~130 MB model cache into the runtime image.**
- Design: entry 17 (lines 763–768): builder stage sets `FASTEMBED_CACHE_PATH`, copies model cache (~130 MB) into runtime image; cold start must not re-download.
- Repo: `Dockerfile:1–47` builder runs `python -m vg.rag.builder` (downloads model at build time) but never sets `FASTEMBED_CACHE_PATH` nor copies a model cache to the runtime stage; runtime image gets only `chroma_db` and site-packages.
- Impact: blocks Phase 1 entry 17 until implemented; the cold-start guarantee in the verification plan depends on it (and on verifying the cache knob against the installed fastembed version — see nit below).

### 🟢 Nit findings

**F-10 — `.env.example` stale "MUDDL API Keys" header (entry 9) — cosmetic.**
- Repo: `.env.example:1` `# MUDDL API Keys (BYOK — Bring Your Own Key)`. Plan acknowledges this is stale; trivial edit.

**F-11 — `QUICKSTART.md:8` `cd vg` invocation is already correct from repo root (contradicts entry 7's premise).**
- Design: entry 7 (lines 680–684): "Fix the broken `cd vg` invocation → run `python run.py` from the repo root."
- Repo: `QUICKSTART.md:8` already says `cd vg && pip install -r requirements.txt` — from the repo root this is correct (`run.py` exists at root). Minor doc alignment needed, not a blocker.

**F-12 — `README.md` still documents CLI invocations (entry 6) — doc-only, non-blocking.**
- Repo: `README.md` documents CLI usage; plan wants web UI + programmatic `analyze()` documented instead.

### Build-readiness verdict (codebase-details)

**Not implementation-ready as specified.** Step 0 deletions (entries 1–4) are actionable immediately — `cli.py`, `vg-main/`, `testapp/`, and the six root orphan test files all exist; nothing imports `cli.py`. Step 0 entries 8–9, 11–12 (file creation/modification work: `incidents/__init__.py`, `schema.py`, `store.py`, `scoring.py`, `match.py`, `gaps.py`, `research.py`, tests, `data/incidents/README.md`) can be authored against the design today.

**Phase-by-phase blocking:**

| Blocked phase/entry | Blocked by | Resolution needed |
|---|---|---|
| Phase 4 entry 31 `research.py` (and entry 34 tests) | `search_news()` contract (critic M1 / F-01 below) | `search_news()` returns a display string, not structured URL+snippet results, plus a 24-hour date filter useless for historical research. Research.py cannot fulfill its contract ("claim text from the snippet, sources entry with URL and date") without a structured search helper or a string-parser deviation — neither exists today |
| Phase 1 entry 14 corpus (`data/incidents/*.json × 30` + excerpt files) | F-02 | Curator must author 30 cards + excerpt files; Nvidia held-out demo cannot run until then |
| Phase 3 entries 21–28 | F-04–F-07 | Dispatch table, flag gate, 501, UI overhaul all require edits to existing files |
| Phase 1 entry 15 `config.py` keys | — | Implementable today (add six keys); no external blocker |
| Phase 1 entry 16 `build_incidents()` | F-02 | Can't pre-bake a meaningful corpus until entry 14 exists |
| Phase 2 entry 19 `scoring.py` + entry 20 fixtures | — | Implementable today; fixtures need analog cards authored (corpus dependency) |

Phase 4 specifically is blocked until the search-contract issue resolves, because `research.py`'s contract cannot be satisfied by the current `search/web.py` ("use as-is" claim contradicted by the actual API).

---

## Reviewer B: egm-style (plan writing)

Terminology, phase names, module names, and file numbers 10–34 internally consistent; every number appears exactly once; phase headings match build-sequence order; cut list reconciles with the target list; cross-references (file 5 at L649; files 18/20 at L979) resolve correctly; no dangling internal references.

### 🟡 Major finding

**Duplicate docstring correction (L761, entry 16 vs L688–690, entry 8).**
- Entry 16 (`rag/builder.py` Modify) carries parenthetical "(Also corrects the stale `python -m veritas.rag.builder` docstring.)" — but Step 0 entry 8 already performs this exact correction on the same file ("Correct stale `python -m veritas.rag.builder` to `python -m vg.rag.builder`"). Ambiguous ownership: an implementer could apply the edit twice or treat one entry as superseding the other.
- Fix: remove the parenthetical from entry 16 (ownership belongs to entry 8) or state explicitly that entry 16's change is conditional on entry 8 not having run.

### 🟢 Nit findings

- **Undefined `v1` reference (L900, entry 30 `gaps.py`):** "claim contradiction, mechanical only in v1" — `v1` never defined in the audit scope (feature version? schema version?). Define or drop.
- **Ambiguous file count (L951, Explicit cuts):** "to keep the package at six files" — seven `.py` modules are created (`__init__.py`, `schema.py`, `store.py`, `scoring.py`, `match.py`, `gaps.py`, `research.py`). Six only if `__init__.py` is excluded; state that explicitly.
- **Filler phrasing (L954, Explicit cuts):** `"just in case"` is informal filler inconsistent with the plan's dry engineering tone. Rephrase to "No reduced agent panel is kept in incident mode as a precaution" or simply "No reduced agent panel in incident mode."

---

## Consolidated Stage 9 verdict

**Not yet implementation-ready.** The design's plan structure is sound (correct phase order, coherent file numbering, accurate cut list, well-scoped verification plan), but execution cannot proceed end-to-end until:

1. **Search contract (critic M1 / codebase-details F-01):** `search/web.py`'s `search_news()` must return structured `{url, snippet, date}` results (or research.py must deviate from "use as-is"), and the 24-hour date filter must not apply to historical research. Blocks Phase 4 entry 31 and its tests (entry 34).
2. **Corpus authoring (F-02):** 30 curated cards + excerpt files must be committed by the curator before Phase 1 entry 14 and the Nvidia held-out demo (verification) can run.
3. **Existing-file edits (F-03–F-09):** config keys, server dispatch table + flag gate, `main.py` strip + incidents auto-build + flag check, `api/index.py` 501, UI overhaul, `build_incidents()`, Dockerfile model-cache pre-bake. Block Phase 3 entries 21–28.
4. **Docstring ownership (style Major):** remove the duplicate correction from entry 16.

Entries actionable immediately against the current repo: Step 0 deletions (1–4), docstring fix (8), `.env.example`/`QUICKSTART.md`/`README.md` doc edits (6–9), and all new `incidents/` package files (11–12, 19–20 logic, 30–34 logic) can be authored today as spec. The remaining work is repo-prep plus the curator-authored corpus — none of it requires redesign.
