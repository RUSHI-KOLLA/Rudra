# Consolidated Review Report

**Target:** `/home/rushi/vg/docs/designs/incident-memory.md` (1010 lines; FeatureRange 1..625 / DetailedRange 626..1010)
**Preset:** Consolidated report with all review rubrics (uninterrupted full flow)
**Date:** 2026-11-18
**Stages executed:** 5 (Zoom Out + Inventive Catalyst) → 6 (Comprehension) → 7 (Critic round 1) → 8 (Intermediate Zoom Out) → 9 (Implementation Readiness)
**Stage outputs:** `zoom_out_report.md`, `comprehension_report.md`, `critic_report.md`, `intermediate_zoom_out_report.md`, `implementation_readiness_report.md`
**GoldfishContext:** none (document contains no links; author provided no additional context files)

## Merge rules (orchestrator)

- Every finding below carries severity (🔴 Blocker / 🟡 Major / 🟢 Nit), source stage + reviewer, affected scope, discrepancy, and rationale.
- Cross-reviewer duplicates were merged into one cluster (marked). Elephant pre-categorization: all 34 major clusters are PROPOSE FIX — none contestable on facts (each repo-verified by at least one reviewer, or an internal contradiction visible in the document). Five clusters embed an author decision between alternatives and are flagged "author choice".
- Nit clusters are copy edits only; none block build.
- Stage 8 found no new findings — the document was unchanged between Stage 5 and Stage 8, so all Stage 5 findings persist unchanged. Stage 8's verdict is folded into Stage 5's clusters.
- Stage 9 reviews the DetailedRange only (lines 626–1010); its majors reference the same defects found at spec scope plus repo-readiness items (config keys, dispatch table, corpus absence, `search/web.py` contract).

## Totals

| Severity | Count | Notes |
|---|---|---|
| 🔴 Blocker | 0 | All five stages agree: no blocker |
| 🟡 Major | 34 clusters | 19 from Stage 7 (deduplicated), overlapping Stage 5, plus 9 Stage 9 repo-readiness majors |
| 🟢 Nit | ~50 clusters | Copy edits, terminology, headings, drift |

**Bottom line:** no blockers; the zero-agent redesign is directionally right; implementation must not start until the author-decision clusters (C5, C6, C8, C10, C13) are resolved and the two hard preconditions (search contract C1/F-01; corpus authoring F-02) land.

## Majors — Stage 5 (Zoom Out / Inventive Catalyst), Clusters C1–C6

### C1 — 🟡 Major — The `search/web.py` contract does not match the research loop's needs
**Sources:** Zoom-out Finding 1; Inventive Catalyst Finding 8; re-verified at Stage 8
**Scope:** Data flow (lines ~327–338); Integration points (`search/web.py`, lines ~381–384); `incidents/research.py` spec (lines ~907–919); Target Files list (no `search/web.py` entry)
**Discrepancy:** The design claims `search_news()` is the loop's only search dependency, used "as-is" with unchanged behavior, returning "URL + usable snippet" per question. Verified reality: `search_news()` returns a pre-formatted display string (titles/URLs interleaved, content truncated to 220 chars, plus a Tavily AI `SUMMARY:` line), hard-appends `" latest news"` to every query, enforces a 24-hour `from_date` filter (fallback only fires on exception, never on empty results), and silently re-searches on exception — a second Tavily call. Consequences: research.py must regex-parse its own dependency's human-readable output; historical/expected-evidence gap questions (filings older than a day, board statements, market reactions) systematically return nothing and surface as "no source available"; `sources[].date` cannot be populated; and the fallback path breaks the exact "one search per question" arithmetic the verification plan asserts. `search/web.py` appears nowhere in the Target Files list (files 1–34).
**Author resolution needed:** Add a structured variant to `search/web.py` (e.g. `search_news_structured()` returning `{url, snippet, published_date}` dicts with a date-window parameter whose default preserves debate behavior exactly), list it in the Target Files / integration points, state the recency-window policy per gap type, and count any fallback re-search in the per-query dedupe ledger. Do not leave the design claiming a contract the shared module doesn't provide.
**Stage 8 re-verification:** unchanged — `search/web.py` still returns a display string; the gap persists.

### C2 — 🟡 Major — The zero-token structural mode gate is speculative machinery for a mode that ships disabled
**Sources:** Zoom-out Finding 2; Inventive Catalyst Finding 4
**Scope:** CUJ 2 (lines ~151–161); `match.py` gate spec (line ~814); `app.js` override logging (line ~862); Alternatives H/I
**Discrepancy:** `debate_enabled` defaults off. While off, the Debate option is inert and everything routes to incident mode — the gate's pre-selection (input shape, date patterns, entity density) buys nothing a visible manual selector doesn't already provide; its value materializes only if/when the flag is turned on. Meanwhile the gate adds a heuristic classifier, one-click override + override logging, and test surface to v1 — YAGNI at this stage.
**Author resolution needed:** Split CUJ 2: manual selector at v1 (Incident | Debate; Debate inert while flag off), defer the zero-token structural gate behind the flag until it is first enabled. Keep the mechanical incident-shape precondition before the research loop (Inventive Catalyst F-4) so incident-side search quota is protected regardless of gate timing.

### C3 — 🟡 Major — Boundary with `core/pattern_engine.py` is undefined — a third pattern subsystem is being created silently
**Sources:** Zoom-out Finding 3
**Scope:** Component layout import rule (lines ~184–187); Alternative D (lines ~484–494); Future Improvements fallback (lines ~616–618)
**Discrepancy:** The repo will then contain three mechanical "pattern/analogy" layers: `core/upset_patterns.py` (hand-written upset DB feeding debate grounding), `core/pattern_engine.py` (pre-LLM linguistic/economic/temporal detection feeding the debate), and the new `incidents/` corpus. The design addresses only the first (Alternative D + recorded fallback); it never mentions `pattern_engine.py`. The 3-import isolation rule makes the runtime boundary clear but not the architectural boundary: without an explicit sentence, a future contributor gets two places to wire "historical analogies" and will guess.
**Author resolution needed:** One paragraph stating that the incidents corpus does not feed `pattern_engine.py`'s analogy path, and extend the "component reframe fallback" to cover it (or record why it can't). Architectural-boundary gap only — not a redesign.

### C4 — 🟡 Major — `core/upset_patterns.py` is mischaracterized in the Problem statement
**Sources:** Zoom-out Finding 4; Inventive Catalyst Finding 9 (corroborated by repo read)
**Scope:** The Problem, gap 1 (lines ~33–36)
**Discrepancy:** The claim "hand-written structural patterns with no dates, actors, or outcomes" is wrong on two of three counts: `UpsetEntry` carries `year` (date) and `actual_outcome` (outcome) for each of ~11 cases; what it lacks is **actors** and — decisively — the **domain** (elections/geopolitics, not corporate exits) and **structural field matching** (keyword-list based). The conclusion ("no incident memory for founder-CEO-exit-style incidents") stands, but the supporting facts are verifiably wrong, weakening the reuse analysis for any reader who checks the repo.
**Author resolution needed:** Tighten wording to "election-domain, keyword-matched, no actor/structural fields".

### C5 — 🟡 Major — Token bound ignores the extraction repair retry (author choice)
**Sources:** Zoom-out Finding 6
**Scope:** G4 (line ~88); NFR Token overhead (line ~565); CUJ 1 (line ~148) vs. extraction spec (lines ~806–811)
**Discrepancy:** "≤ ~2.3k tokens per fresh incident" is stated unconditionally, but extraction allows one repair retry — worst case roughly doubles the extraction call. CUJ 1's "Then" assertion ("≤ ~2.3k LLM tokens consumed") is untestable as written.
**Author resolution needed:** State steady-state ≤ ~2.3k with a retry-bounded worst case (~2×), or restate CUJ 1's token assertion. Author choice: either phrasing is acceptable.

### C6 — 🟡 Major — Per-query hash-drift check is optional complexity — drop it (author choice)
**Sources:** Zoom-out Finding 7
**Scope:** Data stores contract (line ~293); `store.py` spec (lines ~722–724)
**Discrepancy:** Server-start rebuild is sub-second at 50 records and picks up hand edits; a per-query hash check against top-20 candidates guards a multi-writer scenario that doesn't exist in a single-user tool. The design marks it "optional" itself.
**Author resolution needed:** Make it a cut (§ Explicit cuts) and delete the corresponding test obligation. Author choice: cut vs. keep-as-optional.

---

## Majors — Stage 7 (Critic round 1), remaining clusters C14–C22

### C14 — 🟡 Major — Outcome write path contradicts Risk 1 ("curated 30 are safe")
**Sources:** Critic `egm-structural` M3; corroborated by comprehension finding on `record_outcome`
**Scope:** CUJ 3 (lines ~165–168); outcome path data flow (lines ~337–338); Known Risk 1 (lines ~578–582)
**Discrepancy:** Risk 1 says curated records are safe because they are hand-authored while auto-extracted provisional records carry model error. But the outcome path writes model-extracted outcome fields directly into JSON records — including curated ones — with no confirm/review step (unlike the paste path, which has confirm-before-save). Model error can therefore corrupt exactly the records Risk 1 declares safe.
**Author resolution needed:** Add a confirm/review step (or provisional-outcome-with-revert) to the outcome path, or amend Risk 1.

### C15 — 🟡 Major — Stop-rule wording omits its own two-round cap
**Sources:** Critic `egm-style` M3
**Scope:** G7 (lines ~101–102); plan stop rule (~916–919)
**Discrepancy:** G7 states "the loop stops only when nothing further can be closed with available sources — never on a model's judgement," but the same sentence grants "maximum two rounds," and the plan's stop rule is a three-way disjunction (nothing closable / all remaining gaps no-source / two rounds elapsed). "Only when" states one disjunct as the sole condition.
**Author resolution needed:** Rewrite: "the loop stops when nothing further can be closed with available sources, every remaining open gap has returned 'no source available', or the two-round cap is reached — never on a model's judgment."

### C16 — 🟡 Major — "Same story" dedupe overclaims the byte-identical mechanism
**Sources:** Critic `egm-style` M4
**Scope:** CUJ 4 (line ~176); cache mechanism (lines ~296–297)
**Discrepancy:** "paste-hash dedupe prevents the same story from entering twice" — but the mechanism keys on `(sha256(paste), corpus_version)` and catches only byte-identical re-pastes; a re-worded duplicate is not caught, and the spec never states whether the cache blocks the provisional save path.
**Author resolution needed:** Narrow the claim to byte-identical re-paste; state what (if anything) stops a re-worded duplicate from being saved.

### C17 — 🟡 Major — Tag cascade is ambiguous at its decision boundaries
**Sources:** Critic `egm-style` M9; corroborated by comprehension F21
**Scope:** Claim tagging — precedence cascade (lines ~264–273)
**Discrepancy:** Three problems a mechanical rule cannot have: (1) rule 2's "primary source directly cited in the paste" is undefined at claim vs paste level; (2) rule 3's "No primary document" is undefined when a primary source is cited but its excerpt is not stored; (3) rule 4 (`inferred` + `supports`) is near-unreachable as ordered — rule 3 (`reported_unconfirmed`) fires first for any conclusion drawn from other claims without a primary document.
**Author resolution needed:** State the decision procedure unambiguously — what each condition is evaluated against, per claim, and the actual precedence.

### C18 — 🟡 Major — "Nothing existing breaks on deploy" contradicts the flag-off change
**Sources:** Critic `egm-style` M2; Inventive Catalyst Finding 7
**Scope:** Non-Functional Requirements Rollout & Rollback (lines ~570–574); `/api/analyze` gating (~351)
**Discrepancy:** The rollout claims additive safety "with the debate flag defaulting off so nothing existing breaks on deploy," while flag-off `/api/analyze` returns `debate_disabled` and Step 0 deletes `cli.py`/`vg-main/`/`testapp/`/orphan tests. The default-off decision is fine; the safety claim contradicts it.
**Author resolution needed:** Either default `debate_enabled: true` (preserve current behavior) or restate rollout honestly: existing `/api/analyze` callers receive `debate_disabled` until the flag is set.

### C19 — 🟡 Major — `retrieval_debug` is a load-bearing, tested response field that is never defined
**Sources:** Critic `egm-structural` M6; design nit N9; comprehension F19
**Scope:** CUJ 1 (line ~148); data flow (line ~335); plan files 21/28 (~813, ~927)
**Discrepancy:** `retrieval_debug` appears as a contract element of every match response, including test assertions, but no section defines its contents or shape. The per-component contributions / `WEIGHTS_VERSION` audit story (lines ~393–397) implies what belongs in it, but a fresh engineer cannot implement or test it from this document.
**Author resolution needed:** Define the `retrieval_debug` shape (top-20 list? per-component contributions? distances?) and state it once.

### C20 — 🟡 Major — G8's "reserved for forecast questions only" has no enforcement mechanism
**Sources:** Critic `egm-structural` M8
**Scope:** G8 (lines ~103–105); Non-Goals (~113–115); API changes (~351–355); Alternative H (~523–533)
**Discrepancy:** The flag-on path "behaves exactly as today … and serves forecast questions only," but today's `/api/analyze` accepts any question type, the LLM-classifier router was rejected (Alternative H), and the structural gate only pre-selects a visible selector with a one-click override. Nothing restricts the debate pipeline to forecast questions.
**Author resolution needed:** Reword G8/Non-Goals as a default-routing policy, or define the enforcement mechanism.

### C21 — 🟡 Major — No incident-shape precondition before the research loop runs
**Sources:** Inventive Catalyst Finding 4
**Scope:** Structural mode gate (`match.py`); Alternative H rejection rationale; gap detector 1
**Discrepancy:** The design protects debate quota from misroutes ("a misrouted paste must not burn search quota") but leaves incident quota defenseless: a question-shaped input pre-set to incident mode spends the full extraction call, produces a near-empty card, and gap detector 1 (empty match-relevant fields) fires on almost every field — templated questions burning up to 5–10 Tavily searches chasing evidence for an event that never happened.
**Author resolution needed:** Add a zero-token incident-shape precondition before the loop runs: require at least one datable event plus a named actor/org in the extracted card; otherwise skip the research loop and render the empty fields as gaps (the silence line names them). Mechanical, no tokens, no model.

### C22 — 🟡 Major — Gap type 4 (no match in memory) is structurally un-closable by search
**Sources:** Inventive Catalyst Finding 5; Zoom-out Finding H (Stage 8 re-verification)
**Scope:** `gaps.py` detector 4 (~901–905); `research.py` (~907–919); scoring tiers/no-match state (~404–406)
**Discrepancy:** "Each gap emits a templated question text, a search query, and the closure target it can fill" is applied uniformly to a gap that is structurally un-closable by search — gap 4 is corpus absence, not evidence absence; no web search can add a card to memory. Its closure target is undefined, so `research.py` either wastes one search per no-match paste or dereferences a missing target.
**Author resolution needed:** Exempt gap 4 from the one-search rule — its closure is the panel copy plus weak-tier context, already specified. Optionally invert the waste into value: gap 4's query hunts for candidate historical analogs to suggest as future corpus records (suggestions only, never evidence, never written back).


### C7 — 🟡 Major — "Curated-first matching" is load-bearing and undefined
**Sources:** Comprehension Finding 1
**Scope:** G5 (line ~93); CUJ 4 (line ~175); Risk 1 (line ~581)
**Discrepancy:** "Curated-first matching" is used three times as a design property but never defined. A fresh reader cannot tell whether provisional records participate in matching/scoring/base-rate counts before promotion, or only curated records match until promotion. Risk 1 cites it as a mitigation for poisoned provisional records — which requires the exclusion reading. Behaviorally significant either way.
**Author resolution needed:** State the exact mechanism in schema/store sections: e.g., provisional records excluded from candidate retrieval and base-rate denominators until promoted, OR provisional records match with a "provisional match" label in results and `retrieval_debug`, and rewrite the growth promise honestly as two-step. Author choice between readings.

### C8 — 🟡 Major — "Raises 3–5 research questions" asserts a floor the mechanics cannot guarantee
**Sources:** Comprehension Finding 2
**Scope:** Overview (line ~19); CUJ 1 (line ~145); data flow (line ~328); file 30 (lines ~894–905)
**Discrepancy:** The loop emits one question per detected gap, capped at `questions_per_round` = 5 (0–5 per round, ≤ 10 total). Nothing guarantees a floor of 3; a complete card with zero gaps legitimately raises zero questions. The Overview and CUJ 1 state "3–5 research questions were raised" as definite observable behavior, which fails on the clean-card case.
**Author resolution needed:** Restate as "up to five per round — one per detected gap, ranked and capped; ≤ 10 total across two rounds" in Overview and CUJ 1.

### C9 — 🟡 Major — "as of <date>" stamp date source is unspecified
**Sources:** Comprehension Finding 3
**Scope:** "as of <date>" stamp — lines 18, 80, 145, 414; file 21 (line ~814)
**Discrepancy:** The stamp is a headline honesty feature ("as-of dating" is in the revision note), but the document never says which date it is: query time, latest `recorded_at` in the corpus, or something else. Two readers can implement different semantics; a cached repeat-paste response compounds the ambiguity.
**Author resolution needed:** Pin the stamp's semantics once (response-level, query time or corpus freshness) and state what a cached repeat-paste response stamps.

### C10 — 🟡 Major — `corpus_version` in the repeat-cache key is never defined
**Sources:** Comprehension Finding 4
**Scope:** Data stores (lines ~296–297); data flow (line ~314)
**Discrepancy:** The repeat cache is keyed on `(sha256(paste), corpus_version)`, but `corpus_version` is never defined — not among the six new config keys, not derived anywhere. Cache-invalidation correctness is unverifiable: under-invalidation serves stale matches after corpus growth or outcome recording; over-invalidation silently voids the "0 tokens and 0 searches on repeat paste" guarantee.
**Author resolution needed:** Define `corpus_version` precisely (e.g., sha256 over sorted `(incident_id, record_hash)` pairs), name its home module, and state the bump rule under `store.py`'s lock.

### C11 — 🟡 Major — `outcome-Jaccard` is structurally zero on the fresh-paste path; "sharpening" overstated
**Sources:** Comprehension Finding 5 (paralleled by critic C5 at Stage 7)
**Scope:** Scoring weights (lines ~393–397); worked example (~427–437); schema (lines ~239–243)
**Discrepancy:** `Jaccard(∅, ·) = 0` and outcome data is "empty for live pastes," so a fresh paste scores outcome-Jaccard = 0 against every candidate regardless of how rich candidates' recorded outcomes are. The Overview's "recorded outcomes sharpen ranking" holds only for re-matches between two outcome-bearing cards — inert for exactly the traffic the feature targets. Separately, which field(s) feed `outcome-Jaccard` (constraint_types? actors? summary?) is never stated.
**Author resolution needed:** Define the Jaccard input field(s); restate the sharpening claim honestly; zero the outcome component during `calibrate_weak_floor()` so the threshold is fitted to the production regime.

### C12 — 🟡 Major — `summary_embed` "canonical fields" never enumerated
**Sources:** Comprehension Finding 6
**Scope:** Schema (lines ~247–248); file 11 (lines ~714–715); file 27 (line ~869)
**Discrepancy:** The embedding template is "a fixed Python template over canonical fields," a template change forces full re-embed — but the canonical field list is never enumerated. File 27 adds only that outcome fields are excluded. File 30's "match-relevant set" is a hint, not a definition; this template drives the 0.25-cosine component (largest weight, carrier of the "same pattern, not same words" thesis).
**Author resolution needed:** Enumerate the exact fields in the template (in the schema section) and pin it in the fixture test.

### C13 — 🟡 Major — `actor_roles` closed vocabulary never enumerated
**Sources:** Comprehension Finding 7
**Scope:** Schema (lines ~220–221); worked example (~431); files 13–14
**Discrepancy:** `actor_roles` is a "CLOSED vocabulary in a constants module," but its values are never enumerated — only seven incidental examples appear in the Petraeus row. Curated cards are hand-authored (files 13–14, not by this implementation) and scoring depends on exact-string role matching, so the closed set is load-bearing and unavailable to reader or curator.
**Author resolution needed:** Enumerate the `actor_roles` values inline or in `schema.py` (file 11), since the plan folds the constants module into `schema.py`.

## Majors — Stage 9 (Implementation Readiness), Clusters B-1 through B-15

### B-1 — 🟡 Major — Step 0 entry 1 (`cli.py` deletion): deletion-safety claim unverified
**Sources:** `egm-implementation-readiness` B-1
**Scope:** Step 0 entry 1 (lines ~639–643)
**Discrepancy:** The plan asserts "nothing imports this file (verified)" but documents no verification record, no importer list, and no acceptance criteria. The implementer cannot re-verify from the plan alone; deleting an imported file breaks the build.
**Author resolution needed:** Enumerate the importers checked (e.g., "grep for cli.py across *.py found zero matches") so the precondition is checkable. Blocks Step 0 gate — no `incidents/` code may be written until resolved.

### B-2 — 🟡 Major — Entry 12 (`incidents/store.py`): no typed error class or 503 mapping specified
**Sources:** `egm-implementation-readiness` B-2
**Scope:** Entry 12 (lines ~717–729)
**Discrepancy:** "unavailability raises a typed error → 503 upstream, never an empty result set" — but no error class is named, no module it lives in, no `except` → 503 mapping code in `api/server.py` or `match.py`.
**Author resolution needed:** Name the error class, where it's raised (embedding init? per-query?), and how the API layer converts it to HTTP 503. Blocks file 12 and file 22 (503 handling).

### B-3 — 🟡 Major — Entry 15 (`config.py`): no env-var names, dataclass placement, or `get_config` wiring
**Sources:** `egm-implementation-readiness` B-3
**Scope:** Entry 15 (lines ~746–753)
**Discrepancy:** Six new keys listed (`incidents_data_path`, `incidents_collection`, `incident_weak_threshold`, `debate_enabled`, `max_research_rounds`, `questions_per_round`) with defaults, but no env-var names (e.g. `VG_INCIDENTS_DATA_PATH`?), no field placement in the `Config` dataclass, no `get_config()` `os.getenv` lines.
**Author resolution needed:** Specify env names and wire them into `Config`/`get_config`. Blocks file 15 and every phase that reads these keys (files 19, 21, 23, 31).

### B-4 — 🟡 Major — Entry 16 (`rag/builder.py`): `build_all()` merge design unspecified
**Sources:** `egm-implementation-readiness` B-4
**Scope:** Entry 16 (lines ~755–761)
**Discrepancy:** "build_incidents() added to build_all() — read the JSON corpus, embed summary_embed, upsert into incidents cosine collection." But current `build_all()` reads `*.txt` personality files and chunks them; incidents are JSON cards at `data/incidents/*.json` with a different document model. No code shape for merging the two patterns, no collection-name constant, no whether the embedding model is shared or re-instantiated.
**Author resolution needed:** Specify how `build_all()` merges personality and incident indexing. Blocks file 16 and file 17 (Dockerfile bake).

### B-5 — 🟡 Major — Entry 17 (`Dockerfile`): no exact edits for `FASTEMBED_CACHE_PATH` / model cache
**Sources:** `egm-implementation-readiness` B-5
**Scope:** Entry 17 (lines ~763–768)
**Discrepancy:** "Builder stage sets FASTEMBED_CACHE_PATH and copies the model cache (~130 MB) into the runtime image." The current Dockerfile has no `FASTEMBED_CACHE_PATH`, no model-cache copy, and the runtime stage copies only site-packages, `/app/vg`, and `chroma_db`. No `ENV`, `COPY`, or stage-placement instructions given.
**Author resolution needed:** Specify where to add the `ENV` var, which `COPY` lines to add, and whether the cache path persists across builder/runtime stages. Blocks file 17 and file 12 (fastembed model availability at runtime).

### B-6 — 🟡 Major — Entry 21 (`incidents/match.py`): extraction call pattern lacks prompt, schema, client binding
**Sources:** `egm-implementation-readiness` B-6
**Scope:** Entry 21 (lines ~802–816)
**Discrepancy:** "one small-model call (async allam-2-7b, JSON mode response_format={…}, explicit 45–60s timeout, one repair retry, tolerant-parse fallback)" — but no system prompt, no extraction response schema (which fields, types), no binding to `AsyncGroqLLMClient` vs `get_async_llm_client`, no what `allam-2-7b` maps to (`config.model_small`?), no extractor function signature.
**Author resolution needed:** Specify the prompt, schema, client binding, and extractor signature. Blocks file 21, file 10 (`__init__.py` re-exports), and file 28 (tests stub the extractor).

### B-7 — 🟡 Major — Entry 22 (`api/server.py`): dispatch-table code not specified
**Sources:** `egm-implementation-readiness` B-7
**Scope:** Entry 22 (lines ~818–828)
**Discrepancy:** "do_POST hardcoded comparison → dispatch table ({"/api/analyze": …, "/api/incident-match": …, "/api/incident-outcome": …})" — but no handler function signatures, no routing code, no how `do_POST` branches, no body parsing per route. Current `do_POST` (lines 83–149) hardcodes `/api/analyze`.
**Author resolution needed:** Write the dispatch-table conversion. Blocks file 22.

### B-8 — 🟡 Major — Entry 23 (`main.py`): incidents auto-build code not specified
**Sources:** `egm-implementation-readiness` B-8
**Scope:** Entry 23 (lines ~830–837)
**Discrepancy:** "run_web startup gains the incidents analogue of the RAG auto-build: ensure the incidents collection exists / rebuild from JSON before serving" — but no call site in `run_web`, no function called, no error handling, no whether it runs on every start or only when missing. Current `run_web` (lines 221–238) builds RAG only when `chroma.sqlite3` is absent; the plan says incidents rebuild always fires.
**Author resolution needed:** Specify the call site, function, error handling, and trigger condition. Blocks file 23.

### B-9 — 🟡 Major — Entry 24 (`api/index.py`): incident-route 501 code not specified
**Sources:** `egm-implementation-readiness` B-9
**Scope:** Entry 24 (lines ~839–843)
**Discrepancy:** "Both incident routes return a clean 501" — but `api/index.py` (lines 54–57) returns 404 for any non-`/api/analyze` path already; adding incident routes returning 501 requires path registration and response code. No code given.
**Author resolution needed:** Specify the route branching. Blocks file 24.

### B-10 — 🟡 Major — Entries 25–26 (`api/static/index.html`, `app.js`): no markup, CSS, or JS given
**Sources:** `egm-implementation-readiness` B-10
**Scope:** Entries 25–26 (lines ~845–863)
**Discrepancy:** UI changes described only by intent ("Mode selector", "multiline paste box", "full-height overlay panel", "extract → review → confirm → render"). No HTML, no CSS class names, no JS function signatures, no event wiring. Current `index.html` is a Three.js/GSAP app with a 350px aside.
**Author resolution needed:** Specify the UI component contract. Blocks files 25–26 (the largest surface, least specified).

### B-11 — 🟡 Major — Entry 27 (`record_outcome`): triage trigger `N` unspecified
**Sources:** `egm-implementation-readiness` B-11
**Scope:** Entry 27 (lines ~865–873)
**Discrepancy:** "if no outcomes have been recorded after N weeks of use, freeze the sharpening loop" — `N` is undefined, no timer persistence mechanism, no where "weeks of use" is stored, no what "freeze" means in code.
**Author resolution needed:** Define `N`, storage, and freeze behavior. Blocks file 27.

### B-12 — 🟡 Major — Entry 32 (`match.py` modify): loop integration sites unspecified
**Sources:** `egm-implementation-readiness` B-12
**Scope:** Entry 32 (lines ~921–927)
**Discrepancy:** "Loop integration between first score and response: gaps → questions → research → write-back → re-embed → re-score → final tiers" — but no call sites inside `match()`, no where re-embed is triggered, no response audit structure shape.
**Author resolution needed:** Specify call sites and response-audit structure. Blocks file 22 (match.py, already created in Phase 3).

### B-13 — 🟡 Major — Entry 31 (`incidents/research.py`): write-back field mapping unspecified; `search_news` returns a string, not structured URL+snippet
**Sources:** `egm-implementation-readiness` B-13
**Scope:** Entry 31 (lines ~907–919)
**Discrepancy (mechanical mismatch):** "written back through existing card fields: claim text from the snippet, a sources entry with the URL and date… gap's target field filled where derivable." But `vg.search.web.search_news()` (verified at `search/web.py:38–113`) returns a single formatted string, not structured `{url, snippet}` objects. No parsing function, no field-to-card mapping ("where derivable" is undefined), no date extraction rule.
**Author resolution needed:** Add a structured search variant or specify the string parser and field mapping. Blocks file 31, file 34 (tests), and the Verification Plan search-quota audit. **Hard mechanical blocker for Phase 4.**

### B-14 — 🟡 Major — Entries 33–34 / Verification Plan: zero-model-call assertion mechanism unspecified
**Sources:** `egm-implementation-readiness` B-14
**Scope:** Entries 33–34 (~930–944); Verification Plan (~983–989)
**Discrepancy:** "zero-model-call assertions on gaps.py and research.py — the tests prove it" — but no mechanism (AST scan for LLM imports? monkeypatched client that raises? call-count spy?) is given.
**Author resolution needed:** Specify the assertion mechanism. Blocks files 33–34 and the Verification Plan gap-loop gate.

### B-15 — 🟡 Major — Verification Plan: token audit and search-quota audit have no measurement method
**Sources:** `egm-implementation-readiness` B-15
**Scope:** Verification Plan (~1000–1003)
**Discrepancy:** "token audit from Groq response usage (≤ ~2.3k LLM tokens fresh…)" and "search-quota audit (≤ 10 Tavily searches per fresh paste)" — but no instrumentation, no counter, no test code, no how to measure tokens from Groq response usage.
**Author resolution needed:** Specify telemetry. Blocks the Verification Plan and E2E/Manual smoke.

## Majors — Stage 9 (Codebase Details), Clusters F-02 through F-09

### F-02 — 🟡 Major — No `data/incidents/` corpus exists; 30 curated cards must be hand-authored before scoring can be exercised
**Sources:** `egm-codebase-details` F-02
**Scope:** Entries 13–14 (lines ~731–744): `data/incidents/README.md` plus `data/incidents/*.json` × 30 curated cards (user-authored, not implementation), outcomes pre-filled, claims tagged with real source refs; Nvidia excluded as held-out demo #31
**Discrepancy:** Repo `data/` contains only `sample_data.py`. No `data/incidents/` directory, no corpus JSON files, no excerpt files — including `data/incidents/nvidia_2026/sources/nvidia_2026_sources.md` designated at design lines ~53–73, which is not committed.
**Author resolution needed:** Until those 30 JSON files + excerpt files are authored (a curator task), Phase 1–2 test suites can only run against empty/fixture corpora, and the E2E smoke ("Nvidia demo only after the 30-card corpus exists", Verification Plan ~1003–1006) cannot be executed as specified.

### F-03 — 🟡 Major — `config.py` lacks all six new incident keys; paths must be absolute and package-root-anchored
**Sources:** `egm-codebase-details` F-03
**Scope:** Entry 15 (lines ~746–753)
**Discrepancy:** `config.py:12–82` defines exactly the existing keys (groq/tavily/gemini API keys, model selection, rate limiting, generation, RAG, debate, search). None of the six incident keys exist. There is no package-root anchor helper; `chroma_db_path: str = "./chroma_db"` (line 42) is CWD-relative, contradicting the plan's own "never CWD-relative" rule.
**Author resolution needed:** Entry 15 is implementable today (add keys), but store/match cannot resolve `data/incidents` paths CWD-independently until it lands.

### F-04 — 🟡 Major — `api/server.py` `do_POST` has no dispatch table; incident routes `POST /api/incident-match` and `POST /api/incident-outcome` do not exist
**Sources:** `egm-codebase-details` F-04
**Scope:** Entry 22 (lines ~818–828)
**Discrepancy:** `api/server.py:83–87` hardcodes `if parsed.path != "/api/analyze":` → 404. No dispatch table, no incident routes, no `debate_enabled` gate, no `needs_manual_entry` or 503-with-reason typing.
**Author resolution needed:** Blocks Phase 3 entries 21–22 until implemented.

### F-05 — 🟡 Major — `main.py` is not stripped to the keep-list; no incidents auto-build in `run_web`; no `debate_enabled` check in `analyze_async`/`analyze`
**Sources:** `egm-codebase-details` F-05
**Scope:** Entry 23 (lines ~830–837); entry 5 (lines ~665–672)
**Discrepancy:** `main.py:36–57` `analyze_async` unconditionally constructs a `DebateCoordinator` (lines 44–51) with no flag check. `run_web` (lines 221–238) has the RAG analog only (Chroma sqlite check); no incidents collection rebuild. `run_cli` (lines 170–219), `print_report` (lines 60–148), `byok_setup` (lines 151–154), and `--cli/--json/--basic` handling (lines 174–182, 243–246) all remain.
**Author resolution needed:** Blocks Phase 3 entry 23; post-edit regression check needed against `run.py`/Dockerfile CMD/Procfile (they import only `run_web`/`analyze_async`, so low risk, must still be tested).

### F-06 — 🟡 Major — `api/index.py` returns 404 for all non-`/api/analyze` paths; no clean 501 for incident routes
**Sources:** `egm-codebase-details` F-06
**Scope:** Entry 24 (lines ~839–843)
**Discrepancy:** `api/index.py:54–57` `if self.path != "/api/analyze":` → 404. No 501 handling.
**Author resolution needed:** Blocks Phase 3 entry 24.

### F-07 — 🟡 Major — Web UI (`api/static/index.html`, `app.js`) posts only to `/api/analyze`; no incident overlay, mode selector, or extracted-fields review state
**Sources:** `egm-codebase-details` F-07
**Scope:** Entries 25–26 (lines ~845–863)
**Discrepancy:** `api/static/app.js:392–426` submits `fetch("/api/analyze", {question, enhanced})` only. `api/static/index.html:251–263` `.app-side` is a fixed 350px panel. No mode selector, no paste box, no overlay, no `tag · source` rendering.
**Author resolution needed:** Blocks Phase 3 entries 25–26; this is the largest surface and least specified (no component contract given for the overlay).

### F-08 — 🟡 Major — `rag/builder.py` needs `build_incidents()` added to `build_all()`; docstring fix tracked separately at entry 8
**Sources:** `egm-codebase-details` F-08
**Scope:** Entry 16 (lines ~755–761)
**Discrepancy:** `rag/builder.py:39–98` `build_all()` only builds the five `PERSONALITY_COLLECTIONS`; no `build_incidents()`, no `incidents` collection. Docstring stale `veritas.rag.builder` confirmed at line 3 (matches entry 8).
**Author resolution needed:** Entry 16 is implementable today, but entry 16's parenthetical ("Also corrects the stale docstring") duplicates Step 0 entry 8. The builder stage can't pre-bake an empty corpus meaningfully until entry 14's corpus exists (F-02).

### F-09 — 🟡 Major — `Dockerfile` does not set `FASTEMBED_CACHE_PATH` or copy the ~130 MB model cache into the runtime image
**Sources:** `egm-codebase-details` F-09
**Scope:** Entry 17 (lines ~763–768)
**Discrepancy:** `Dockerfile:1–47` builder runs `python -m vg.rag.builder` (downloads model at build time) but never sets `FASTEMBED_CACHE_PATH` nor copies a model cache to the runtime stage; runtime image gets only `chroma_db` and site-packages.
**Author resolution needed:** Blocks Phase 1 entry 17 until implemented; the cold-start guarantee in the Verification Plan depends on it (and on verifying the cache knob against the installed fastembed version).

## Nits — consolidated copy-edit clusters (~50 raw findings, ~12 clusters)

All copy edits; none block build. Full detail remains in the stage reports.

| Cluster | Scope | Representative items |
|---|---|---|
| N1 | Headings / counts | "Known Risks (**the three weakest points**)" introduces four items (line ~576); header revision note says "six-file package" while layout creates seven `.py` modules (`__init__.py` + six) — align both |
| N2 | Wrong-direction pointers | Line ~446–447 "anchor case **below**" — section is above (lines ~50–73); line ~308 forecast branch labeled "(flag on)" while the box beneath handles both flag states |
| N3 | Revision residue | Line ~402 "the former optional gloss is cut" — gloss doesn't exist in this document; line ~220 "CLOSED vocabulary in a constants module" — plan folds constants into `schema.py` and cuts `constants.py`; line ~572 "(and flip the flag back)" — flag defaults off and isn't part of rollback |
| N4 | Terminology inconsistency | "why-it-matches" vs "why-matches" vs "why/breaks bullets"; "`outcomeJ`" vs "outcome-Jaccard" vs "typed outcome term"; "NVIDIA" vs "Nvidia"; "≤4,000 characters" vs "≤4k chars" vs "4,000-character"; "≥30 curated records" vs "the 30 curated records" |
| N5 | Spelling / grammar | "judgement" (line ~102; plan line ~919) vs American "behavior"; "The templated questions also read stiff" → "read as stiff"; "a clean 501" → "an explicit 501" |
| N6 | Overstated absolutes | "a hard ceiling" (line ~278) excepted two sentences later; "steady-state cost" (line ~88) never distinguished from non-steady; "on the order of tens of seconds" understates ~80s worst case (45–60s extraction + up to 10 searches); "should cost an order of magnitude less" — 16.5k → ~2.3k is ~7×, under one order of magnitude |
| N7 | Undefined / drifted terms | "v1" (line ~900) never defined; "structural signature" (line ~408) appears once; "dominant incident" (line ~809) has no selection rule; "top-3-equivalent emphasis" (line ~858) undefined; "claims tagged below `documented`" (line ~413) implies an unordered ranking; "same-event" grouping for contradiction detection (timeline `claim_ids` is a hint, not a rule); `sources[].type` allowed values unstated |
| N8 | Unspecified destinations | "override logging" (line ~862) names no destination (response field? server log?); "record it in a dev-requirements note" (line ~981) says where; "one-line migration plus reindex and is called out as such" (lines ~573–574) is self-referential |
| N9 | Inaccurate / stale pointers | Additional Resources (lines ~605–606) lists `core/debate.py` — Technical Plan never cites that path; it names `EnhancedDebateCoordinator` in `vg/core/enhanced_debate.py`; `concepts_brief.md` cited as authoritative but `docs/` contains only this design document; "behavior byte-equivalent" (line ~669) mixes file-bytes and behavior |
| N10 | Spec/plan hedge mismatch | "on server start (and optionally per query against top-20 candidates)" (line ~293) vs plan's unconditional drift check (plan lines ~722–724) — remove "optionally" or make the plan conditional |
| N11 | Tag/scope drift | G2 "exactly one provenance tag … with its source" (lines ~81–84) — `inferred` claims carry `supports` claim ids rather than a source; `speculative` claims may carry none; CUJ 4 "paste-hash dedupe prevents the same story from entering twice" overstates byte-identical mechanism |
| N12 | Stamp scope | Overview line ~18 and CUJ 1 lines ~144–145 attach "as of <date>" to different item sets; response carries a single response-level `as_of` (~205, ~334–335) — state once |

## Majors — Stage 9 (Implementation Readiness / Zero-Decision Rule), Clusters M-1 through M-12

Additional readiness findings from `egm-implementation-readiness` (Part 2), framed against the Zero-Decision Rule: the plan leaves architectural/code-level choices to the implementer rather than specifying them.

### M-1 — 🟡 Major — Config path pattern contradicts `chroma_db_path` precedent
**Scope:** Entry 15 (`config.py`) vs entry 8 (`rag/builder.py` docstring) vs `config.py:42` (`chroma_db_path: str = "./chroma_db"`)
**Discrepancy:** Entry 15 demands new paths be "absolute and package-root-anchored, never CWD-relative," but the pre-existing RAG path is CWD-relative, and no anchor helper is specified.
**Resolution:** Pick one pattern for the whole file (absolute anchored at package root, or CWD-relative like the rest) and state it once.

### M-2 — 🟡 Major — Dockerfile cache-copy directives missing
**Scope:** Entry 17 (`Dockerfile`)
**Discrepancy:** "Builder stage sets FASTEMBED_CACHE_PATH and copies the model cache (~130 MB)" — no `ENV`, `COPY`, or stage-placement instructions given; current Dockerfile copies only site-packages, `/app/vg`, and `chroma_db`.
**Resolution:** Specify exact `ENV`/`COPY` lines and stage placement.

### M-3 — 🟡 Major — `summary_embed` canonical field list missing; re-embed scope contradictory
**Scope:** Entry 11 (`schema.py`); entry 27 (`record_outcome`); entry 32 (`match.py` modify)
**Discrepancy:** Entry 11 never lists which canonical fields compose `summary_embed`. Entry 27 says outcome fields are excluded (no re-embed); entry 32 says research-filled fields change `summary_embed` (re-embed triggered). Contradiction unresolved; the implementer cannot know which writes trigger re-embed.
**Resolution:** Enumerate exact fields in entry 11; state which are in/out of scope for re-embed; mark research write-back fields as re-embed-triggering or not.

### M-4 — 🟡 Major — Extractor injection pattern unspecified
**Scope:** Entry 21 (`match.py`); entry 28 (`test_incident_match.py`)
**Discrepancy:** Entry 21 requires an "injectable extractor so tests never hit Groq" but gives no DI pattern (constructor param, module override, env switch). File 28 says "Stub extractor + fake embedder" without saying how it's wired in.
**Resolution:** Specify injection mechanism in entry 21 (e.g., `extract_card(paste, extractor=real_extractor)` parameter).

### M-5 — 🟡 Major — `score()` signature and cosine source unspecified
**Scope:** Entry 19 (`scoring.py`)
**Discrepancy:** Scoring is "pure… no I/O, no LLM, no Chroma imports" yet computes cosine (`1 − distance`) and Jaccard; "cosine injected as a parameter" is stated but no signature or type given for how the caller obtains and passes cosine.
**Resolution:** Give exact `score(cosine: float, card, candidate) -> dict` signature; specify match.py obtains cosine from store.py's query embedding.

### M-6 — 🟡 Major — `calibrate_weak_floor()` invocation point unspecified
**Scope:** Entry 19 (`scoring.py`) vs entry 15 default 0.45 "until calibrated"
**Discrepancy:** "Run once post-corpus" — no CLI, no endpoint, no hook in `main.py`/`run_web` to invoke it.
**Resolution:** Specify how/when it runs (one-off script, or `run_web` startup guard) before Phase 2 is complete.

### M-7 — 🟡 Major — Outcome reindex timing undefined
**Scope:** Entry 27 (`store.py` modify); CUJ 3
**Discrepancy:** `record_outcome()` does "JSON-only update… hash refresh"; CUJ 3 says future matches gain the outcome term "immediately." No mechanism stated for how a live match picks up a newly recorded outcome (reindex trigger, hash drift at query, or next start).
**Resolution:** Specify whether `record_outcome` triggers `rebuild_index()` or relies on per-query hash-drift check against top-20 candidates.

### M-8 — 🟡 Major — `record_outcome` triage trigger `N` undefined (duplicate of B-11)
**Scope:** Entry 27
**Discrepancy:** "if no outcomes have been recorded after N weeks of use, freeze the sharpening loop" — `N` undefined, no timer persistence, no freeze behavior in code.
**Resolution:** Define `N`, storage, and freeze behavior. (Duplicate of B-11; counted once.)

### M-9 — 🟡 Major — Step 0 entry 4 per-file actions not enumerated
**Scope:** Step 0 entry 4 (root test files audit/move/delete)
**Discrepancy:** "Audit each against `tests/`: delete where coverage duplicates `tests/`… move any unique coverage" — no criteria for "duplicates" vs "unique coverage," no per-file action for the six root test files.
**Resolution:** Enumerate per-file action (delete/move) for each of the six root test files, or give an explicit mechanical rule.

### M-10 — 🟡 Major — Verification Plan test-instrumentation gaps
**Scope:** Verification Plan (~1000–1003); entries 18, 20, 33–34
**Discrepancy:** (a) Entry 18 downgrade-rule test needs excerpt-file fixture setup unspecified; (b) entry 20 pass criterion "correct top-5 ordering" needs expected ordering stated as test input; (c) debate-flag test "counting constructor calls" — no mechanism specified; (d) "pytest is dev-only" — no instruction to add `dev-requirements.txt` or where `pytest` is installed for CI.
**Resolution:** Specify fixtures, expected ordering, constructor-call counting mechanism, and dev-dependency placement.

### M-11 — 🟡 Major — `retrieval_debug` shape undefined (duplicate of C-19)
**Scope:** CUJ 1 (~148); data flow (~335); plan files 21/28
**Discrepancy:** Required response field with test-shape assertions, never defined.
**Resolution:** Define shape once. (Duplicate of C-19; counted once.)

### M-12 — 🟡 Major — UI cannot read `debate_enabled` (duplicate of B-1)
**Scope:** Entries 25–26; explicit cuts (line ~968)
**Discrepancy:** "the panel reads `debate_enabled` from config" but browser-side JS cannot read server config without a fetch or a baked-in page value; no endpoint for it.
**Resolution:** Specify mechanism (fetch endpoint or baked-in value). (Duplicate of B-1/C-9; counted once.)

## Traceability Matrix — raw finding → consolidated action

| Stage | Raw finding ID | Consolidated cluster | Severity | Action owner | Blocked phase |
|---|---|---|---|---|---|
| 5 | Zoom-out F1 | C-1 | 🟡 | Author | Phase 4 (file 31) |
| 5 | Zoom-out F2 | C-2 | 🟡 | Author | Phase 3 (file 21/26) |
| 5 | Zoom-out F3 | C-3 | 🟡 | Author | Docs only |
| 5 | Zoom-out F4 | C-4 | 🟡 | Author | Docs only |
| 5 | Zoom-out F6 | C-5 | 🟡 | Author (choice) | Docs only |
| 5 | Zoom-out F7 | C-6 | 🟡 | Author (choice) | Docs only |
| 5 | Catalyst F5 | C-22 | 🟡 | Author | Phase 4 (file 31) |
| 5 | Catalyst F6 | C-13 | 🟡 | Author | Phase 3 (file 21/26) |
| 5 | Catalyst F7 | C-18 | 🟡 | Author | NFR |
| 6 | Comprehension F1 | C-7 | 🟡 | Author (choice) | Phase 1 (schema/store) |
| 6 | Comprehension F2 | C-8 | 🟡 | Author | Docs only |
| 6 | Comprehension F3 | C-9 | 🟡 | Author | Phase 3 (file 21) |
| 6 | Comprehension F4 | C-10 | 🟡 | Author | Phase 1 (store.py) |
| 6 | Comprehension F5 | C-11 | 🟡 | Author | Phase 2 (file 19) |
| 6 | Comprehension F6 | C-12 | 🟡 | Author | Phase 1 (file 11) |
| 6 | Comprehension F7 | C-13 | 🟡 | Author | Phase 1 (file 11) |
| 7 | Design M1 | C-1 | 🟡 | Author | Phase 4 (search contract) |
| 7 | Design M2 | C-2 | 🟡 | Author | Phase 3 (routing) |
| 7 | Design M3 | C-3 | 🟡 | Author | Docs only |
| 7 | Design M4 | C-4 | 🟡 | Author | Docs only |
| 7 | Design M5 | C-11 | 🟡 | Author | Phase 2 (file 19) |
| 7 | Design M6 | C-6 | 🟡 | Author | Phase 1 (schema/store) |
| 7 | Design M7 | C-12 | 🟡 | Author | Phase 1 (file 11) |
| 7 | Design M8 | C-2 | 🟡 | Author | Phase 3 (routing) |
| 7 | Design M9 | C-10 | 🟡 | Author | Corpus authoring |
| 7 | Design M10 | C-10 | 🟡 | Author | Status/Docs |
| 7 | Design M11 | C-11 | 🟡 | Author | Docs only |
| 7 | Design M12 | C-12 | 🟡 | Author | NFR |
| 7 | Design M13 | C-13 | 🟡 | Author | Phase 3 (confirm flow) |
| 7 | Structural M1 | C-8 | 🟡 | Author | Docs only |
| 7 | Structural M2 | C-13 | 🟡 | Author | Phase 3 (confirm flow) |
| 7 | Structural M3 | C-14 | 🟡 | Author | Phase 3 (outcome path) |
| 7 | Structural M4 | C-4 | 🟡 | Author | Docs only |
| 7 | Structural M5 | C-1 | 🟡 | Author | Phase 4 (search contract) |
| 7 | Structural M6 | C-19 | 🟡 | Author | Phase 3 (file 21/28) |
| 7 | Structural M7 | C-10 | 🟡 | Author | Phase 1 (store.py) |
| 7 | Structural M8 | C-20 | 🟡 | Author | NFR |
| 7 | Structural M9 | C-10 | 🟡 | Author | Corpus authoring |
| 7 | Style M1 | C-4 | 🟡 | Author | Docs only |
| 7 | Style M2 | C-18 | 🟡 | Author | NFR |
| 7 | Style M3 | C-15 | 🟡 | Author | Docs only |
| 7 | Style M4 | C-16 | 🟡 | Author | Docs only |
| 7 | Style M5 | C-12 | 🟡 | Author | Docs only |
| 7 | Style M6 | C-17 | 🟡 | Author | Schema |
| 7 | Style M7 | C-4 | 🟡 | Author | Docs only |
| 7 | Style M8 | C-18 | 🟡 | Author | NFR |
| 7 | Style M9 | C-17 | 🟡 | Author | Schema |
| 7 | Style M10 | C-9 | 🟡 | Author | Phase 3 (file 21) |
| 7 | Style M11 | C-14 | 🟡 | Author | NFR heading |
| 7 | Style M12 | C-8 | 🟡 | Author | Docs only |
| 8 | All Stage 5 findings | persist unchanged | — | — | — |
| 9 | Readiness B-1 | B-1 | 🟡 | Author | Step 0 gate |
| 9 | Readiness B-2 | B-2 | 🟡 | Author | Phase 1 (file 12) / Phase 3 (file 22) |
| 9 | Readiness B-3 | B-3 / M-1 | 🟡 | Author | Phase 1 (file 15) |
| 9 | Readiness B-4 | B-4 / M-4 | 🟡 | Author | Phase 2 (file 19) / Phase 3 (file 21) |
| 9 | Readiness B-5 | B-5 / M-2 | 🟡 | Author | Phase 1 (file 17) |
| 9 | Readiness B-6 | B-6 | 🟡 | Author | Phase 3 (file 22) |
| 9 | Readiness B-7 | B-7 | 🟡 | Author | Phase 3 (file 23) |
| 9 | Readiness B-8 | B-8 | 🟡 | Author | Phase 3 (file 24) |
| 9 | Readiness B-9 | B-9 | 🟡 | Author | Phase 3 (files 25–26) |
| 9 | Readiness B-10 | B-10 | 🟡 | Author | Phase 3 (files 25–26) |
| 9 | Readiness B-11 | B-11 / M-8 | 🟡 | Author | Phase 3 (file 27) |
| 9 | Readiness B-12 | B-12 | 🟡 | Author | Phase 3 (file 22) |
| 9 | Readiness B-13 | B-13 / C-1 | 🟡 | Author | Phase 4 (file 31) — hard blocker |
| 9 | Readiness B-14 | B-14 | 🟡 | Author | Verification Plan (files 33–34) |
| 9 | Readiness B-15 | B-15 | 🟡 | Author | Verification Plan / E2E |
| 9 | Codebase F-02 | F-02 | 🟡 | Curator | Corpus before Phase 1 entry 14 |
| 9 | Codebase F-03 | F-03 / B-3 | 🟡 | Author | Phase 1 (file 15) |
| 9 | Codebase F-04 | F-04 / B-6 | 🟡 | Author | Phase 3 (file 22) |
| 9 | Codebase F-05 | F-05 / B-7 | 🟡 | Author | Phase 3 (file 23) |
| 9 | Codebase F-06 | F-06 / B-8 | 🟡 | Author | Phase 3 (file 24) |
| 9 | Codebase F-07 | F-07 / B-9/B-10 | 🟡 | Author | Phase 3 (files 25–26) |
| 9 | Codebase F-08 | F-08 | 🟡 | Author | Phase 1 (file 16) |
| 9 | Codebase F-09 | F-09 / M-2 | 🟡 | Author | Phase 1 (file 17) |
| 9 | Readiness M-1 | B-3 | 🟡 | Author | Phase 1 (file 15) |
| 9 | Readiness M-2 | B-5 | 🟡 | Author | Phase 1 (file 17) |
| 9 | Readiness M-3 | B-3 / M-3 | 🟡 | Author | Phase 1 (file 11/12) |
| 9 | Readiness M-4 | B-4 | 🟡 | Author | Phase 2 (file 19) |
| 9 | Readiness M-5 | B-6 | 🟡 | Author | Phase 2 (file 19) |
| 9 | Readiness M-6 | B-7 | 🟡 | Author | Phase 2 (file 19) |
| 9 | Readiness M-7 | B-11 | 🟡 | Author | Phase 3 (file 27) |
| 9 | Readiness M-9 | B-9 | 🟡 | Author | Step 0 entry 4 |
| 9 | Readiness M-10 | B-15 | 🟡 | Author | Verification Plan |

## Final verdict

**Not yet implementation-ready.** Zero blockers; 34 major clusters (all PROPOSE FIX; 5 author-choice clusters: C-5, C-6, C-7, C-10, C-11); roughly 50 nit clusters, all copy edits.

**Preconditions to implementation (must land before Phase 1 code is written — recall Step 0 is a hard gate):**

1. **Search contract (C-1 / B-13 / M-4):** `search/web.py` must return structured `{url, snippet, date}` results (or research.py must deviate from "use as-is"), plus a recency-window policy per gap type. Hard mechanical blocker for Phase 4 entry 31.
2. **Corpus authoring (F-02 / C-10):** Curator commits the 30-title list + 30 JSON cards + excerpt files before scoring can be exercised; Nvidia held-out demo deferred until then.
3. **Config keys (B-3 / F-03):** Six new keys with env-var names and package-root path resolution.
## Majors — Stage 9 (Implementation Readiness / Zero-Decision Rule), Clusters BLOCKER 1–16, MAJOR 17–24

This reviewer applied the Zero-Decision Rule: a competent engineer unfamiliar with the codebase must be able to execute without guessing, asking clarifying questions, or making independent design choices. The plan fails this standard — **16 BLOCKERs, 8 MAJORs, 3 NITs**. These supersede the earlier B-1..B-15 / M-1..M-12 cluster incorporation (mapped in the traceability matrix below).

### BLOCKER 1 — 🔴 Entry 10: `incidents/__init__.py` — Public surface not specified
**Scope:** Entry 10 (lines ~699–704)
**Discrepancy:** "Re-export the public surface (schema types, store functions, match orchestration entry)" — no export names, no `__all__`, no import statements specified. The implementer must decide what constitutes the public surface.
**Resolution:** Specify exact export names, import statements, and whether `__all__` is defined.

### BLOCKER 2 — 🔴 Entry 11: `incidents/schema.py` — Entire data model left to implementer
**Scope:** Entry 11 (lines ~706–715)
**Discrepancy:** Card dataclass — no field names, types, or defaults. Strict enums/closed vocabularies — no enum names or allowed values. Mechanical tag cascade — not defined (what tags, triggers, rules). JSON round-trip validation — no specification of which fields are validated or `ValueError` format. `summary_embed` template — no template string or canonical field list. Claim ids `c1…cn` — ambiguous id format.
**Resolution:** Complete dataclass definition, enum classes with values, tag cascade algorithm, exact template string, JSON schema with examples.

### BLOCKER 3 — 🔴 Entry 12: `incidents/store.py` — Persistence layer entirely unspecified
**Scope:** Entry 12 (lines ~717–729)
**Discrepancy:** JSON card file schema/naming convention unspecified. Chroma collection schema (metadata fields, embedding dimension, ID format) unspecified. `record_hash (sha256)` — hash of what input? Drift check — no behavior specified on drift (rebuild? error? warn?). `;`-joined list metadata — which fields, what encode/decode functions? Paste-hash repeat cache — no key, TTL, max size, eviction policy. Typed error → 503 — no exception class name. `rebuild_index()` — no batch size, upsert behavior, partial-failure handling.
**Resolution:** Full JSON card schema, Chroma metadata schema, `record_hash` input, drift behavior, `;`-joined field list, cache config, exception class names, `rebuild_index()` details.

### BLOCKER 4 — 🔴 Entry 15: `config.py` — New keys lack implementation pattern
**Scope:** Entry 15 (lines ~746–753)
**Discrepancy:** Six new keys listed but no env-var names, no `os.getenv` pattern vs dataclass field, no placement in `config.py`, no absolute path resolution code.
**Resolution:** Exact `config.py` code additions with env var names, `os.getenv` defaults, path resolution pattern.

### BLOCKER 5 — 🔴 Entry 16: `rag/builder.py` `build_incidents()` — Integration unspecified
**Scope:** Entry 16 (lines ~755–761)
**Discrepancy:** No integration point in `build_all()` (before/after personality collections? same loop?). Chroma collection schema for incidents unspecified. Document ID generation unspecified. Metadata per incident unspecified. Re-run behavior (upsert? delete-first?) unspecified. Duplicate docstring-correction ownership with Entry 8.
**Resolution:** `build_incidents()` function body, integration point, Chroma schema, ID generation, metadata, re-run behavior; resolve Entry 8 vs Entry 16 duplication.

### BLOCKER 6 — 🔴 Entry 19: `incidents/scoring.py` — Scoring algorithm entirely unspecified
**Scope:** Entry 19 (lines ~780–790)
**Discrepancy:** `candidate` data structure unspecified. Per-component return type/structure unspecified. Strong vs weak vs no-match classification rules unspecified. **`WEIGHTS` dict values not specified at all.** Why-match/where-it-breaks templates unspecified. Base-rate formula and fallback trigger unspecified. `calibrate_weak_floor()` invocation mechanism unspecified.
**Resolution:** Complete `WEIGHTS` dict, component formulas, tier rules, return structure, explanation templates, base-rate formula, calibration invocation.

### BLOCKER 7 — 🔴 Entry 21: `incidents/match.py` — Extraction and orchestration unspecified
**Scope:** Entry 21 (lines ~802–816)
**Discrepancy:** No extraction prompt, no output JSON schema, no field mapping to card fields. "dominant incident" selection algorithm unspecified; rejection structure unspecified. `needs_manual_entry` return structure and `_raw/` spool naming unspecified. `extract_outcome()` schema unspecified. Structural mode gate — no specification of what it does or how it decides; unclear what coordinator is being gated in a zero-agent design.
**Resolution:** Extraction prompt, output schema, dominant-incident algorithm, `needs_manual_entry` structure, `extract_outcome()` schema, mode gate implementation.

### BLOCKER 8 — 🔴 Entry 22: `api/server.py` — Dispatch table and response schemas unspecified
**Scope:** Entry 22 (lines ~818–828)
**Discrepancy:** No handler signatures, no request/response body schemas. X-API-Key is Groq-scoped but incident mode uses zero LLM calls — requiring a Groq key for incident matching is contradictory and unexplained. Typed failure responses — no body schemas, no status code constants.
**Resolution:** Dispatch table code, handler signatures, request/response JSON schemas, X-API-Key clarification.

### BLOCKER 9 — 🔴 Entries 25–26: UI (`api/static/index.html`, `app.js`) — No output contract or state machine
**Scope:** Entries 25–26 (lines ~845–863)
**Discrepancy:** The match output contract JSON schema is never defined anywhere in the plan. Mode selector inert state unspecified (disabled/hidden/tooltip?). Paste box layout unspecified. Review/edit state machine — no transition conditions or edit validation. "top-3-equivalent emphasis" undefined. No API response consumption logic for `retrieval_debug`, `as_of`, loop audit. No UI error handling for 503, `needs_manual_entry`, "no source available".
**Resolution:** Match output contract JSON schema, UI state machine, panel layout, event flow, error states.

### BLOCKER 10 — 🔴 Entry 27: `record_outcome()` — Outcome schema, triage threshold, freeze mechanism unspecified
**Scope:** Entry 27 (lines ~865–873)
**Discrepancy:** `extract_outcome()` schema unspecified (see BLOCKER 7). `N` in "N weeks of use" unspecified. "freeze the sharpening loop" undefined. No endpoint for triage (cuts say no promote/prune endpoint) — operational mechanism missing.
**Resolution:** Outcome field types, value of `N`, freeze behavior, triage trigger mechanism.

### BLOCKER 11 — 🔴 Entry 28: `tests/test_incident_match.py` — Stubbing and env var mismatch
**Scope:** Entry 28 (lines ~875–881)
**Discrepancy:** "Stub extractor + fake embedder + VG_CHROMA_PATH → tmp dir" but `store.py` uses `config.chroma_db_path`, not `VG_CHROMA_PATH`. No wiring specified. Hash-mismatch simulation unspecified.
**Resolution:** Stubbing mechanism, `VG_CHROMA_PATH` wiring (or use existing config), hash-mismatch simulation.

### BLOCKER 12 — 🔴 Entry 30: `incidents/gaps.py` — Detectors entirely unspecified
**Scope:** Entry 30 (lines ~891–905)
**Discrepancy:** Detector 2 profile mapping — no complete `trigger_type` list, no complete profile mapping (only two examples). Claim/timeline kind taxonomy unspecified. Question templates, search query templates, closure targets — none provided. Ranking tie-breaking unspecified.
**Resolution:** Complete `trigger_type` list, profile mapping, kind taxonomy, templates, closure targets, ranking algorithm.

### BLOCKER 13 — 🔴 Entry 31: `incidents/research.py` — API mismatch and write-back unspecified
**Scope:** Entry 31 (lines ~907–919)
**Discrepancy:** `search_news()` returns a formatted string, not structured URL+snippet — but plan requires "URL + usable snippet." Query dedupe data structure/scope unspecified. Write-back field mapping — which field receives claim text? `sources` entry structure unspecified. "gap's target field filled where derivable" — derivability rules unspecified. Round-2 trigger — "newly exposed closable gaps" undefined.
**Resolution:** Resolve string vs structured result mismatch; dedupe implementation; field mapping; derivability rules; round-2 detection.

### BLOCKER 14 — 🔴 Entry 32: `incidents/match.py` loop integration — Circular dependency with schema
**Scope:** Entry 32 (lines ~921–927)
**Discrepancy:** "re-embed (filled fields change `summary_embed`)" but `summary_embed` template/canonical fields unspecified (BLOCKER 2) — impossible to know which fields trigger re-embed. Loop audit response schema addition unspecified.
**Resolution:** Specify which card fields feed `summary_embed`; loop audit response schema.

### BLOCKER 15 — 🔴 Entry 4: Root test files — "move unique coverage" unspecified
**Scope:** Step 0 entry 4 (lines ~658–663)
**Discrepancy:** "Audit each against `tests/`; delete where coverage duplicates `tests/`… move any unique coverage" — no criteria for duplicates vs unique coverage, no per-file action for the six root test files.
**Resolution:** Enumerate per-file action for each of the six root test files, or give an explicit mechanical rule.

### BLOCKER 16 — 🔴 Build sequence: `incidents/` package location ambiguous
**Scope:** Entries 10–18 (lines ~699–770)
**Discrepancy:** `incidents/` location unspecified — repo root (`/home/rushi/vg/incidents/`, imports as top-level `incidents`) vs inside `vg/` (`vg/incidents/`). Entry 10 says imports limited to `vg.config`, `vg.core.llm_client`, `vg.search.web`, implying incidents is part of the `vg` package. Path ambiguity prevents correct imports.
**Resolution:** Exact filesystem location of `incidents/` and the import path used by all modules.

### MAJOR 17 — 🟡 Entry 4: Root test files — "move unique coverage" unspecified (MAJOR variant)
**Scope:** Step 0 entry 4
**Discrepancy:** Same as BLOCKER 15 but framed as a design decision left to the implementer rather than a hard block.

### MAJOR 18 — 🟡 Entry 14: `data/incidents/*.json × 30` — External dependency, no example
**Scope:** Entry 14 (lines ~739–744)
**Discrepancy:** 30 hand-authored JSON cards are a hard prerequisite but no example card provided. Card schema itself unspecified (BLOCKER 2), so the curator cannot author cards. Nvidia held-out dependency (#31) can't be validated until after the 30 exist.

### MAJOR 19 — 🟡 Entry 19/20: `WEIGHTS` values missing; Nvidia card contradiction
**Scope:** Entries 19–20 (lines ~786–798)
**Discrepancy:** `WEIGHTS` dict values not specified (BLOCKER 6). Test Entry 20 references Nvidia card as fixture, but Entry 14 excludes it until after the 30 exist — test cannot run against a corpus that excludes its primary fixture.

### MAJOR 20 — 🟡 Entry 27: Triage threshold `N` and freeze mechanism undefined (duplicate of BLOCKER 10)
**Scope:** Entry 27
**Discrepancy:** "N weeks of use" — `N` unspecified. "freeze the sharpening loop" undefined. No promote/prune endpoint (cut) — operational triage mechanism missing. (Duplicate of BLOCKER 10.)

### MAJOR 21 — 🟡 Entry 24: `api/index.py` 501 — Response body and routing unspecified
**Scope:** Entry 24 (lines ~839–843)
**Discrepancy:** "Both incident routes return a clean 501" — no response body, no routing addition to existing `handler.do_POST` (currently only handles `/api/analyze`).

### MAJOR 22 — 🟡 Verification Plan: Token audit — no measurement method
**Scope:** Verification Plan (~1000–1002)
**Discrepancy:** "token audit from Groq response usage (≤ ~2.3k LLM tokens fresh…)" — no specification of how tokens are counted, what tool/method, or how "fresh" vs "repeat" is determined in an automated test.

### MAJOR 23 — 🟡 Verification Plan: Search quota — no enforcement mechanism
**Scope:** Verification Plan (~1002–1003)
**Discrepancy:** "≤ 10 Tavily searches per fresh paste" — theoretical max is 10 (5 questions × 2 rounds) but dedupe and round-2 conditions make actual count variable. No enforcement mechanism specified (hard stop? test assertion? runtime limit?).

### MAJOR 24 — 🟡 Verification Plan: Zero-model-call assertions — no mechanism
**Scope:** Verification Plan (~987–989)
**Discrepancy:** "zero-model-call assertions on gaps.py and research.py" — no mechanism specified (import blocking? mock patching? call counting?).

### NIT 25 — 🟢 Entry 2: `vg-main/main.py` diff — No action specified
**Scope:** Entry 2 (lines ~645–649)
**Discrepancy:** "Diff its web-only main.py against root first… then delete" — the diff is performed but no action based on its output. Informational only.

### NIT 26 — 🟢 Entries 8 and 16: Duplicate docstring correction
**Scope:** Entries 8 and 16 (lines ~686–690, ~755–761)
**Discrepancy:** Both claim ownership of the same `veritas.rag.builder` → `vg.rag.builder` docstring fix. Potential for conflicting edits.

### NIT 27 — 🟢 Entry 13: `data/incidents/README.md` — No template provided
**Scope:** Entry 13 (lines ~731–737)
**Discrepancy:** "One template card plus the authoring rules" — but no template card included in the plan. "the 30-title corpus list is committed before scoring design is finalized" — but the 30 titles are not listed anywhere.

## Build-Readiness Verdict (final)

**NOT ACTIONABLE as specified. Requires pre-implementation fixes.**

### Blocked phases/files

| Phase | Blocked until | Blocking findings |
|---|---|---|
| **Step 0** (entries 1–9) | BLOCKER 16, MAJOR 17 | Package location; test file audit spec |
| **Phase 1** (entries 10–18) | BLOCKERS 2–6, 16 | `schema.py`, `store.py`, `__init__.py`, `config.py`, `builder.py` all missing concrete specs |
| **Phase 2** (entries 19–20) | BLOCKERS 6, MAJOR 18–19 | `WEIGHTS` values missing; Nvidia card contradiction; no expected test values |
| **Phase 3** (entries 21–29) | BLOCKERS 7–11 | Extraction prompt, dispatch table, UI contract, outcome schema, triage `N`, test stubbing |
| **Phase 4** (entries 30–34) | BLOCKERS 12–14 | Gap detector profiles, research API mismatch, loop audit schema |

### Required pre-implementation work (in order)

1. Define `incidents/` package location and import path (BLOCKER 16)
2. Complete card schema — all fields, enums, vocabularies, tag cascade, `summary_embed` template (BLOCKER 2)
3. Complete store specification — JSON schema, Chroma metadata, `record_hash`, drift checks, cache config, exceptions (BLOCKER 3)
4. Specify `config.py` additions — env var names, `getenv` patterns, absolute path resolution (BLOCKER 4 / M-1)
5. Specify `build_incidents()` — integration, Chroma schema, ID generation (BLOCKER 5)
6. Complete scoring specification — `WEIGHTS` dict, components, tiers, base-rate formula, `calibrate_weak_floor()` invocation (BLOCKER 6)
7. Specify extraction — prompt, output JSON schema, dominant-incident algorithm, structural mode gate (BLOCKER 7)
8. Specify API dispatch — handler signatures, request/response schemas, X-API-Key implications (BLOCKER 8)
9. Define match output contract — complete JSON schema for all response fields (BLOCKER 9)
10. Specify outcome schema and triage — field types, `N` value, freeze mechanism (BLOCKER 10 / MAJOR 20)
11. Complete gap detectors — `trigger_type` list, profile mapping, question templates, closure targets (BLOCKER 12)
12. Resolve research API mismatch — `search_news()` returns string, need structured URL+snippet (BLOCKER 13 / C-1)
13. Resolve Nvidia card contradiction — include in corpus or remove from test fixtures (MAJOR 19)
14. Specify verification mechanics — token counting, search quota enforcement, zero-model-call assertion (MAJOR 22–24)

Until these are resolved, no engineer can implement from this plan without making independent design choices, violating the Zero-Decision Rule.

## Traceability Matrix — raw finding → consolidated cluster

| Stage | Raw finding ID | Consolidated cluster | Severity |
|---|---|---|---|
| 5 | Zoom-out F1 | C-1 | 🟡 |
| 5 | Zoom-out F2 | C-2 | 🟡 |
| 5 | Zoom-out F3 | C-3 | 🟡 |
| 5 | Zoom-out F4 | C-4 | 🟡 |
| 5 | Zoom-out F6 | C-5 | 🟡 |
| 5 | Zoom-out F7 | C-6 | 🟡 |
| 5 | Catalyst F5 | C-22 | 🟡 |
| 5 | Catalyst F6 | C-13 | 🟡 |
| 5 | Catalyst F7 | C-18 | 🟡 |
| 6 | Comprehension F1 | C-7 | 🟡 |
| 6 | Comprehension F2 | C-8 | 🟡 |
| 6 | Comprehension F3 | C-9 | 🟡 |
| 6 | Comprehension F4 | C-10 | 🟡 |
| 6 | Comprehension F5 | C-11 | 🟡 |
| 6 | Comprehension F6 | C-12 | 🟡 |
| 6 | Comprehension F7 | C-13 | 🟡 |
| 7 | Design M1–M13 | C-1..C-22 | 🟡 |
| 7 | Structural M1–M9 | C-1..C-14 | 🟡 |
| 7 | Style M1–M12 | C-1..C-22 | 🟡 |
| 9 | Readiness B-1 | BLOCKER 15 | 🔴 |
| 9 | Readiness B-2 | BLOCKER 3 | 🔴 |
| 9 | Readiness B-3 | BLOCKER 4 / MAJOR 1 (M-1) | 🔴 |
| 9 | Readiness B-4 | BLOCKER 7 / MAJOR 4 (M-4) | 🔴 |
| 9 | Readiness B-5 | BLOCKER 5 / MAJOR 2 (M-2) | 🔴 |
| 9 | Readiness B-6 | BLOCKER 8 | 🔴 |
| 9 | Readiness B-7 | BLOCKER (entry 23) | 🔴 |
| 9 | Readiness B-8 | MAJOR 21 | 🟡 |
| 9 | Readiness B-9 | BLOCKER 9 | 🔴 |
| 9 | Readiness B-10 | BLOCKER 9 | 🔴 |
| 9 | Readiness B-11 | BLOCKER 10 / MAJOR 20 | 🔴 |
| 9 | Readiness B-12 | BLOCKER 14 | 🔴 |
| 9 | Readiness B-13 | BLOCKER 13 / C-1 | 🔴 |
| 9 | Readiness B-14 | MAJOR 24 | 🟡 |
| 9 | Readiness B-15 | MAJOR 22 | 🟡 |
| 9 | Readiness M-1 | BLOCKER 4 | 🔴 |
| 9 | Readiness M-2 | BLOCKER 5 | 🔴 |
| 9 | Readiness M-3 | BLOCKER 3 / MAJOR 3 (M-3) | 🔴 |
| 9 | Readiness M-4 | BLOCKER 7 | 🔴 |
| 9 | Readiness M-5 | BLOCKER 6 | 🔴 |
| 9 | Readiness M-6 | BLOCKER 6 | 🔴 |
| 9 | Readiness M-7 | BLOCKER 10 | 🔴 |
| 9 | Readiness M-9 | MAJOR 17 | 🟡 |
| 9 | Readiness M-10 | MAJOR 22 / MAJOR 24 | 🟡 |
| 9 | Codebase F-02 | MAJOR 18 | 🟡 |
| 9 | Codebase F-03 | BLOCKER 4 | 🔴 |
| 9 | Codebase F-04 | BLOCKER 8 | 🔴 |
| 9 | Codebase F-05 | BLOCKER (entry 23) | 🔴 |
| 9 | Codebase F-06 | MAJOR 21 | 🟡 |
| 9 | Codebase F-07 | BLOCKER 9 | 🔴 |
| 9 | Codebase F-08 | BLOCKER 5 | 🔴 |
| 9 | Codebase F-09 | BLOCKER 5 / MAJOR 2 | 🔴 |
| 9 | Readiness BLOCKER 1–16 | BLOCKER 1–16 | 🔴 |
| 9 | Readiness MAJOR 17–24 | MAJOR 17–24 | 🟡 |
| 9 | Readiness NIT 25–27 | NIT 25–27 | 🟢 |

### Author-choice clusters (product decisions — implementer cannot resolve)
- **C-5:** Token bound with/without retry-bounded worst case.
- **C-6:** Per-query hash-drift check — cut vs. keep-as-optional.
- **C-7:** Curated-first matching — exclusion vs labeled participation.
- **C-10:** Circular-validation guard — attach the 30-title corpus list to this document, or mark scoring provisional pending committed corpus + calibration (or demote status from Approved).
- **C-11:** Outcome-Jaccard input fields + honest sharpening claim.

### Safe to start now (no new decisions needed)
None under the Zero-Decision Rule — every Phase 1+ file is blocked by a BLOCKER. Step 0 entries 1–3 (deletions of `cli.py`, `vg-main/`, `testapp/`) are safe once BLOCKER 15's verification record is added; entry 4 requires MAJOR 17's per-file enumeration.

### Recommended sequence
Resolve BLOCKER 16 (package location) → BLOCKER 2 (card schema) → BLOCKER 3 (store) → BLOCKER 4 (config) → BLOCKER 5 (builder) → BLOCKER 6 (scoring) → BLOCKER 7 (extraction) → BLOCKER 8 (API dispatch) → BLOCKER 9 (UI contract) → BLOCKER 10 (outcome/triage) → BLOCKER 12 (gap detectors) → BLOCKER 13 (search contract) → BLOCKER 14 (loop integration) → BLOCKER 15/MAJOR 17 (Step 0 test audit) → then author `incidents/` package per build order (cards+schema → scoring → endpoint+panel → gap loop last).

---

## Stage 9 — Final Zero-Decision Rule Dispatch (corroborating findings)

This dispatch corroborates existing clusters and adds four new nits, then delivers the final build-readiness verdict with 17 required pre-implementation fixes in dependency order.

### Corroborating majors (map to existing clusters)

**M16 — Debate-flag constructor-count test mechanism unspecified** (corroborates MAJOR 24 / Verification Plan zero-model-call assertions)
- **Scope:** Verification Plan (~987–989); debate-flag test at line ~993
- **Discrepancy:** Constructor-call counting location/mechanism unspecified; no test file assigned; no mock/patch approach for `EnhancedDebateCoordinator` given. The test must import the coordinator class to count constructions, but incident-mode tests are supposed to never touch Groq/coordinators. Blocks the debate-flag verification gate.
- **Maps to:** MAJOR 24 (verification mechanics).

**M17 — Entry 20 fixture provenance vs entry 14 conflict** (corroborates MAJOR 19 / Nvidia fixture contradiction)
- **Scope:** Entry 20 (~792) vs entry 14 (~739–744)
- **Discrepancy:** Entry 20 says "Nvidia card + five analogs as JSON fixtures," but entry 14 explicitly excludes the Nvidia card (held-out demo #31 after the 30 exist) and states `data/incidents/*.json × 30` are user-authored, not by this implementation. The test fixtures must either exist already (they don't) or be authored by the implementer. Contradiction between entries. Blocks Phase 2 test creation.
- **Maps to:** MAJOR 19.

**M18 — `api/index.py` 501 specification incomplete** (corroborates MAJOR 21)
- **Scope:** Entry 24 (~839)
- **Discrepancy:** "Both incident routes return a clean 501" — only two routes named (`/api/incident-match`, `/api/incident-outcome`), but `do_POST` must also decide what happens to `/api/analyze` on Vercel (still debate-gated? still proxy to Groq?). GET handling for incident routes unspecified. Vercel read-only filesystem vs `PersistentClient` is noted but no build-time or runtime guard is specified. Blocks serverless deployment of incident mode.
- **Maps to:** MAJOR 21.

### New nits

**N1 — Entry 5 keep-list omits `run_cli` removal detail vs `analyze` wrapper** (~665–668)
- Keep-list says `run_cli`, `print_report`, `byok_setup` go; but `analyze()` (line 54–57) calls `from vg.setup import run_async` and `byok_setup` is only used by `run_cli`. If `run_cli` is deleted, `analyze`'s import of `run_async` from `vg.setup` remains used; `byok_setup` becomes dead code in `main.py` itself. Implementer must confirm `analyze()` still works after `--cli` argv handling removal. Low risk.

**N2 — Entry 8 docstring fix duplicates entry 16 correction** (~686–691, ~755–761)
- Both Step 0 entry 8 and Phase 1 entry 16 "correct the stale `python -m veritas.rag.builder` docstring." Redundant instruction; harmless if applied once, but ambiguous which phase owns the final edit.

**N3 — `.env.example` header fix lacks new key placeholders** (~692)
- Entry 9 fixes the "MUDDL API Keys" header but adds none of the six new config keys (`incidents_data_path`, …, `questions_per_round`). New keys are documented nowhere in `.env.example`, so operators won't know to set them. Minor; follows existing pattern but incomplete.

**N4 — Build sequence phrase "no `incidents/` code is written until the tree is single-copy" is not machine-enforced** (~630–633)
- A hard precondition gate stated in prose only; no CI check, pre-commit hook, or test enforces it. Low risk for a small team, but the "hard" characterization is not backed by tooling.

### Final build-readiness verdict

**Is the implementation plan actionable as specified?**  
No. It requires pre-implementation fixes before any `incidents/` code is written.

**Which phases/files are blocked until which findings resolve:**

| Blocked phase/file | Blocked on |
|---|---|
| Step 0 entry 4 (root test delete/merge) | BLOCKER 15 / MAJOR 17 — delete/merge rule |
| Phase 1 `schema.py` (entry 11) | BLOCKER 2 — closed-enum vocabularies/allowed values |
| Phase 1 `store.py` (entry 12) | BLOCKER 3 — cache mechanics, error contract |
| Phase 1 `config.py` (entry 15) | BLOCKER 4 — absolute-path mechanism |
| Phase 1 `rag/builder.py` + `Dockerfile` (entries 16–17) | BLOCKER 5 — signatures, cache path, ENV values |
| Phase 2 `scoring.py` (entry 19) | BLOCKER 6 — exact `WEIGHTS` values |
| Phase 2 `tests/test_incident_scoring.py` (entry 20) | MAJOR 19 — Nvidia fixture conflict |
| Phase 3 `api/server.py` (entry 22) | BLOCKER 8 — typed-response shapes/gating ownership |
| Phase 3 `main.py` (entry 23) | BLOCKER 7 — merge with Step 0 strip |
| Phase 3 `api/static/*` (entries 25–26) | BLOCKER 9 — concrete UI spec |
| Phase 3 `api/index.py` (entry 24) | MAJOR 21 — incomplete 501 spec |
| Phase 4 `gaps.py` (entry 30) | BLOCKER 12 — expected-evidence profile/question text |
| Phase 4 `research.py` (entry 31) | BLOCKER 13 — write-back mapping |
| Phase 4 `match.py` modify (entry 32) | BLOCKER 14 — loop integration |
| Verification (all test files) | MAJOR 22–24 — verification mechanics |

### Required pre-implementation fixes (in dependency order)

1. Restate closed-enum vocabularies and exact field set in `schema.py` entry — preferably inline in this document or with an explicit line-accurate cross-reference inside scope.
2. Publish exact `WEIGHTS` dict + `WEIGHTS_VERSION` semantics in the `scoring.py` entry.
3. Resolve `store.py`↔`match.py` circular import — hoist `extract_outcome` into `schema.py`.
4. Define `N` for the triage trigger.
5. Add a `tests/test_incident_store.py` suite.
6. Replace Step 0 entry 4's judgment language with an explicit delete/keep list.
7. Produce a single coherent `main.py` target state covering both Step 0 strip and Phase 3 additions.
8. Specify `config.py` absolute-path helper and `get_config()` wiring.
9. Define `gaps.py` expected-evidence profile for all trigger types + templated question text + closure targets.
10. Define `research.py` write-back mapping from search answer → card field.
11. Define paste-hash cache `corpus_version` semantics and drift-check algorithm.
12. Name the embedder-down error type and the server→503 translation contract.
13. Specify `build_incidents()` signature, Dockerfile `FASTEMBED_CACHE_PATH` value and cache-copy lines.
14. Add UI markup/event spec or defer Phase 3 UI to a follow-up spec.
15. Clarify `api/index.py` incident-route behavior for both POST and GET.
16. Resolve Nvidia fixture contradiction between entries 14 and 20.
17. Assign debate-flag constructor-count test file and mock approach.

Until items 1–4 (and 9–12 for Phase 4) are resolved, a competent engineer cannot execute lines 626–1010 on the first attempt without guessing — which is precisely what the zero-decision rule forbids. **Recommendation: return the plan to the author with findings marked for rewrite; then re-run Stage 9.**

### Author-choice clusters (product decisions — implementer cannot resolve)
- **C-5:** Token bound with/without retry-bounded worst case.
- **C-6:** Per-query hash-drift check — cut vs. keep-as-optional.
- **C-7:** Curated-first matching — exclusion vs labeled participation.
- **C-10:** Circular-validation guard — attach the 30-title corpus list to this document, or mark scoring provisional pending committed corpus + calibration (or demote status from Approved).
- **C-11:** Outcome-Jaccard input fields + honest sharpening claim.

### Overall conclusion
The egm-review pipeline is complete. The zero-agent redesign is directionally sound with **zero 🔴 Blockers against the architecture itself**, but the implementation plan is **not actionable as specified** — 16 BLOCKERs + 8 MAJORs across Stage 9, plus 19 deduped major clusters from Stages 5–7. The plan must be returned to the author for rewrite of the findings above, followed by a re-run of Stage 9 before any `incidents/` code is written.




