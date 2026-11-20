# Critic Report — Stage 7 (Critic Review, Round 1)

**Target:** `/home/rushi/vg/docs/designs/incident-memory.md` — FeatureRange 1..625
**Reviewers (direct dispatch, parallel):** `egm-design` (feature-spec-standard), `egm-structural` (feature-spec-standard), `egm-style` (persona audit vectors)
**Loop inputs:** SemanticTarget = FeatureRange 1..625; GoldfishContext = none; Round 1 of the antagonistic review loop
**Preset:** Consolidated report with all review rubrics (uninterrupted full flow)
**Date:** 2026-11-18
**Reviewer status:** egm-design = completed; egm-structural = completed; egm-style = completed

## Round-1 outcome

- 🔴 Blockers: **0** (all three reviewers agree)
- 🟡 Majors: **34 raw** (design 13, structural 9, style 12) → **19 distinct clusters after dedup**
- 🟢 Nits: **45 raw** (design 10, structural 14, style 21) → summarized as copy-edit clusters
- Three reviewers independently verified the same repo claims with consistent results (upset-pattern entries carry year/outcome; `search_news()` filters to 24h and returns a display string; the cosine-as-L2 retriever bug is real; the worked example's arithmetic is internally consistent).

## Consolidated FindingsList (majors, deduplicated)

Stable ids: `<reviewer>-r1-<n>` (majors numbered in each reviewer's own order). Stage-5 corroboration noted where the zoom-out reviewers found the same defect.

| Cluster | ID | Finding (one line) | Findings | Stage-5 corroboration |
|---|---|---|---|---|
| C1 | 🟡 | `search/web.py` contract mismatch: display-string return, 24h filter, `" latest news"` suffix, date dropped, silent exception re-search — the loop's "one search per question" and `sources[].date` are unsatisfiable as specified | design-r1-1, structural-r1-5 | zoom-out F1, catalyst F8 |
| C2 | 🟡 | CUJ 2 flag-off semantics self-contradictory (typed response vs incident fallback vs inert option); question-shaped inputs in incident mode unspecified | design-r1-2 | comprehension F8/F9/F11 |
| C3 | 🟡 | "Raises 3–5 research questions" asserts a floor the mechanism cannot produce (0–5/round, ≤10 total) | design-r1-3, structural-r1-1, style-r1-12 | comprehension F2 |
| C4 | 🟡 | `corpus_version` in the cache key is never defined; bump rule and backing store unstated | design-r1-4, structural-r1-7 | catalyst F3, comprehension F4 |
| C5 | 🟡 | Outcome-Jaccard is structurally 0 on the fresh-paste path; "sharpening" overstated; Jaccard input fields undefined; calibration regime mismatch | design-r1-5 | catalyst F1 |
| C6 | 🟡 | "Curated-first matching" load-bearing and undefined (exclusion vs rank-preference readings) | design-r1-6 | catalyst F2, comprehension F1 |
| C7 | 🟡 | `summary_embed` "canonical fields" never enumerated — drives the largest scoring component (0.25 cosine) | design-r1-7 | comprehension F6, style N20 |
| C8 | 🟡 | Zero-token mode gate: no mechanics, no accuracy targets, no routing tests — load-bearing and unmeasured (or defer it while the flag ships off) | design-r1-8 | zoom-out F2, catalyst F4 |
| C9 | 🟡 | Problem statement mischaracterizes `core/upset_patterns.py` (entries carry year + actual_outcome; the real gap is structure/provenance/domain) | design-r1-9, structural-r1-4, style-r1-1 | zoom-out F4 |
| C10 | 🟡 | The doc's own circular-validation guard is breached: weights/threshold/tiers finalized while the 30-title list is uncommitted | design-r1-10, structural-r1-9 | — |
| C11 | 🟡 | Authority chain dead: `concepts_brief.md` pointer unresolvable from docs/ and uncommitted; "stated canonicalization rule" stated nowhere; headline token numbers underived | design-r1-11, style-r1-6 | comprehension F28, structural N11 |
| C12 | 🟡 | Multi-tenant corpus governance unaddressed (shared mutable corpus behind per-request API keys; poisoning beyond model error; spool retention) | design-r1-12 | — |
| C13 | 🟡 | User edits can never affect matching: confirm governs saving only (data flow) vs CUJ 1's confirmed-card matches; no re-score-on-edit path | design-r1-13, structural-r1-2 | catalyst F6 |
| C14 | 🟡 | Outcome write path contradicts Risk 1: model-extracted outcomes write directly into curated JSON with no confirm step | structural-r1-3 | — |
| C15 | 🟡 | G7's "stops only when nothing further can be closed" omits its own two-round cap and the no-source disjunct | style-r1-3 | — |
| C16 | 🟡 | "Same story" dedupe overclaims a byte-identical sha256 mechanism | style-r1-4 | comprehension F24 |
| C17 | 🟡 | Tag cascade ambiguous at decision boundaries (rule 2 claim-level sourcing; rule 3 vs 4 precedence; `inferred` near-unreachable) | style-r1-9 | comprehension F21, design N8 |
| C18 | 🟡 | "Nothing existing breaks on deploy" contradicts the flag-off `debate_disabled` change and Step 0 deletions | style-r1-2 | catalyst F7 |
| C19 | 🟡 | `retrieval_debug` is a load-bearing, tested response field that is never defined | structural-r1-6 | design N9, comprehension F19 |

## Elephant pre-categorization (per cluster)

All 19 clusters are **PROPOSE FIX** — none is contestable on facts (each was repo-verified by at least one reviewer, or is an internal contradiction visible in the document itself). Five clusters embed an author decision between alternatives, flagged below:

- **C6 (curated-first):** decide exclusion (provisional records invisible to retrieval + base rate until promoted) vs labeled participation ("provisional match" tag in results). Either is implementable; the doc must pick one.
- **C8 (mode gate):** defer the gate until `debate_enabled` is first turned on (zoom-out's recommendation; keep a manual selector), or specify it fully (features, decision rule, routing-accuracy fixtures). Either way, add the mechanical incident-shape precondition before the research loop (catalyst F4) so incident-side quota is protected.
- **C13 (confirm vs match):** re-order to extract → confirm → match + loop, or re-run the free local stages on edit (re-embed + re-score cost zero tokens; loop only if match-relevant fields changed).
- **C5 (outcome term):** define the Jaccard inputs, restate the sharpening claim honestly, and zero the outcome component during `calibrate_weak_floor()` so the threshold is fitted to the production regime.
- **C10 (circular validation):** attach the 30-title corpus list to the document (appendix) or mark the scoring section provisional pending the committed corpus + leave-one-out calibration.

Nits consolidate into copy-edit clusters: stale counts/headings (three reviewers), wrong-direction cross-reference, revision residue ("former optional gloss", "constants module"), integration-points header overclaim, config naming asymmetry, diagram label, `_raw/` rebuild exclusion, judgement/judgment spelling, terminology bundle, decorative adverbs/adjectives, tag-ordering phrasing, `max_tokens` pin for extraction, base-rate fallback when `trigger_type` is empty, latency/token-bound honesty (repair retry, ~80s worst case), override-log destination, `VG_CHROMA_PATH` provenance, three-import rule vs `build_incidents()` direction, package-path mapping, freeze-trigger placeholder, artifact-attachment mechanism, "usable/derivable" definitions, outcome-entry-point UI, truncation-vs-rejection normativity.

---

## Reviewer 1: egm-design (Design Critic)

# Design Critic Report — Stage 7 (Critic Review), Round 1
**Target:** `/home/rushi/vg/docs/designs/incident-memory.md`, audit scope lines 1–625 (feature specification)
**Standard:** `feature-spec-standard.md` | **Mode:** REVIEW

## Verification Method

All repo-cited claims were checked against the working tree (`core/upset_patterns.py`, `core/llm_client.py`, `core/enhanced_debate.py`, `agents/config.py`, `rag/builder.py`, `rag/hybrid_retriever.py`, `api/server.py`, `api/index.py`, `api/static/index.html`, `main.py`, `config.py`, `search/web.py`, `Dockerfile`, `requirements.txt`, `docs/`, `data/`).

**Claims verified accurate** (credit where due): the 10-agent count; `EnhancedDebateCoordinator` exists and the debate pipeline's first external act is a Tavily call (`search_news_dual`, 2 calls, `enhanced_debate.py:171–173`); the hardcoded `!= "/api/analyze"` comparison (`api/server.py:85`); the per-request `asyncio.run()` limiter-rebuild bug (`api/server.py:116` + `llm_client.py:64–83`); cosine-space collections built by `rag/builder.py:83–86` vs. the L2-style `1/(1+d)` conversion in `hybrid_retriever.py:222–223`; the stale `veritas.rag.builder` docstring (`rag/builder.py:3`); `build_all()`; the runtime image's missing fastembed cache; the 350px `.app-side` (`index.html:251–255`); `search_news()` existence; G6's zero-new-deps claim (requirements already carry fastembed/chromadb/tavily/aiolimiter/groq); the `chroma.sqlite3`-absent-only RAG check (`main.py:223–233`); the silent-`[]` retriever pattern; the excerpt file's absence from the tree (Open Question is honest). No spec↔plan contradictions were found in the cross-checks performed.

## Blockers

None. No single finding invalidates the architecture; the Majors below must be resolved before implementation, three of them before Phase 1.

## Major Findings

**M1 — 🟡 The Tavily integration contract asserted by the spec does not match the actual `search_news()` API.**
*Scope:* spec lines 381–384, 45–48, 96–102, 278–281, 296–297; repo `search/web.py:38–113`.
*Finding:* The spec claims "the repo's existing Tavily integration is the research loop's only search dependency: one `search_news()` call per question" with usage unchanged, and that answers are written back with "a source and a provenance tag" / `sources` entries carrying URL and date. Verified reality: (a) `search_news()` returns a **formatted display string** ("[i] title / content[:220] / Source: url"), not structured results — research.py must regex-parse its own dependency's human-readable output, a layer the spec never mentions; (b) per-result **date is dropped** (only a header range survives), so the schema's `sources[].date` is unsatisfiable from this function; (c) it hard-filters to the **last 24 hours** (`from_date=yesterday`) and appends `" latest news"` to every query — gap questions referencing pre-paste context (the anchor case's intelligence assessment predates the paste), expected-evidence targets older than a day, and no-match questions against recorded history will systematically return nothing, collapsing the loop to "no source available" exactly where its value was promised; (d) the fallback path (lines 92–101) fires only on exception, not on empty results. `search/web.py` appears nowhere in the target-file list, so the fix contradicts the spec's own "unchanged usage" claim. *Recommendation:* add a structured search function (e.g., `search_news_structured()` returning url/snippet/published_date, with a date-window parameter) to `search/web.py`, list it in the plan, and state the recency-window policy per gap type.

**M2 — 🟡 CUJ 2's "Then" is self-contradictory for the default-off state, and bare-question handling in incident mode is unspecified.**
*Scope:* lines 151–161, 22, 103–105, 113–115, 351–355.
*Finding:* With the flag off, CUJ 2 asserts both that Debate "yields a typed 'debate disabled' response" **and** that "incident mode still serves the question from recorded history." The API change (line 351–355) and plan file 22 implement only the typed response — no incident fallback exists at that route. If instead the gate pre-selects Incident for questions, the spec never says what extraction produces for a question-shaped input that is not an incident report (all match-relevant fields empty? `needs_manual_entry`?). Additionally, "reserved for forecast questions only" (Overview, G8, Non-Goals) and "behaves exactly as today … and serves forecast questions only" (line 353–354) cannot both hold: with the flag on, today's ungated behavior plus a one-click override means an incident paste can run the full debate. No enforcement mechanism is described. *Recommendation:* pick one flag-off semantics for question inputs (typed response only, or gate-forced incident path with defined extraction behavior for non-incident input), and rephrase "forecast questions only" as a UI pre-selection convention, not a system property.

**M3 — 🟡 The "3–5 research questions" invariant is asserted where the mechanism guarantees 0–10.**
*Scope:* lines 19–21, 145–148 (CUJ 1), 328; config `questions_per_round` (5).
*Finding:* The loop yields between 0 questions (complete card, no contradictions, matches exist — no gap fires) and 10 (two rounds × five). CUJ 1's Then clause states "3–5 research questions were raised" as a guaranteed observable for the canonical happy path; the Overview states it as definite behavior. The CUJ as written fails on its own clean-card case. *Recommendation:* restate as "0–5 per round, ≤10 total, only for detected gaps" in Overview and CUJ 1.

**M4 — 🟡 `corpus_version` in the repeat-cache key is never defined.**
*Scope:* lines 296–297, 314; config keys 367–370.
*Finding:* The cache key is `(sha256(paste), corpus_version)`, but `corpus_version` appears nowhere else — not in the config key list, not in the schema, no derivation (record count? corpus content hash? `WEIGHTS_VERSION`?). Cache-invalidation correctness is unverifiable: an under-invalidating definition serves stale matches after corpus growth or outcome recording; an over-invalidating one silently voids the "0 tokens / 0 searches on repeat paste" guarantee. The cache's backing store (memory vs disk) is also unstated. *Recommendation:* define `corpus_version` precisely (e.g., sha256 over sorted `(incident_id, record_hash)` pairs) and name its home module.

**M5 — 🟡 The outcome-sharpening claim is wrong for the primary use case, and `outcome-Jaccard` has no defined inputs.**
*Scope:* lines 24, 92–94 (G5), 169 (CUJ 3), 395–396, 242–243, 437, 415–416.
*Finding:* Scoring defines `Jaccard(∅, ·) = 0` and outcome data is "empty for live pastes." Therefore a fresh paste scores outcome-Jaccard = 0 against every candidate **regardless of how rich the candidates' recorded outcomes are**. The Overview's "recorded outcomes sharpen ranking" and CUJ 3's "future matches involving this record gain the 0.05 outcome term" hold only for re-matches between two outcome-bearing cards — the sharpening loop is inert for exactly the traffic the feature targets. Known Risk 3 calls the term "nearly invisible" but does not disclose that it is *zero* on the main path. Separately, which field(s) feed `outcome-Jaccard` (constraint_types? actors? summary?) is never stated, yet `scoring.py` is claimed "deterministic given (cosine, card, candidate)" and the mechanical explanation bullets derive from per-component diffs. *Recommendation:* define the Jaccard input field(s); either re-scope the sharpening claim honestly or re-specify the component (e.g., compare paste's `resolution` trajectory against candidate's recorded outcome).

**M6 — 🟡 "Curated-first matching" is load-bearing and undefined.**
*Scope:* lines 24, 93–94 (G5), 175–176 (CUJ 4), 580 (Known Risk 1); scoring section 391–417.
*Finding:* The term appears four times and is cited as a *mitigation* against extraction-error poisoning (Risk 1), but no rule is ever given: does it mean (a) only curated records are matchable in v1, or (b) curated records rank above provisional ones? The schema has `status` but the scoring section assigns it no role, and the worked example ignores it. Under reading (b) the poisoning mitigation is nearly vacuous. *Recommendation:* state the exact mechanism (e.g., provisional records excluded from candidate retrieval and base-rate denominators until promoted).

**M7 — 🟡 The `summary_embed` template's field list is never enumerated — and it drives the largest scoring component.**
*Scope:* lines 247–248, 192–193, 425.
*Finding:* `summary_embed` is "a fixed Python template over canonical fields," `trigger` is excluded, and "template change ⇒ full re-embed" — but "canonical fields" is never defined. This template is the input to the 0.25-cosine component (the single largest weight and the carrier of the "same pattern, not same words" thesis). Including surface fields (actors, sector, geography) would reintroduce topic similarity, defeating Alternative A's rejection rationale; excluding them changes cosine's meaning entirely. The worked example's "cosine 0.55 assumed on the structural-template embedding" is unreproducible without the field list. *Recommendation:* enumerate the exact fields in the template (or in the schema section) and pin it in the fixture test.

**M8 — 🟡 The zero-token structural mode gate has zero specification and zero test coverage.**
*Scope:* lines 529–532 (Alternative H rejection), 204–206, 359–363; plan files 21, 28, 33–34.
*Finding:* The gate ("input shape, date patterns, entity density") decides which pipeline consumes quota: a misroute under flag-on sends an incident paste to Tavily + a 16.5k–66.8k-token debate run — the exact failure the design says it exists to prevent (line 362–363). No mechanics, thresholds, examples, accuracy targets, or routing-accuracy tests exist for it (the test files cover the `debate_disabled` response and gap detectors, never gate behavior). A heuristic that is simultaneously load-bearing and unmeasured is an unmitigated risk. *Recommendation:* specify the gate's features and decision rule, add routing-accuracy fixtures (question vs incident pastes) to the test plan, and state the misroute-cost containment (e.g., debate's first search is the only pre-agent quota burn).

**M9 — 🟡 The Problem statement mischaracterizes `core/upset_patterns.py`.**
*Scope:* lines 33–36; repo `core/upset_patterns.py:32–77, 84–402`.
*Finding:* The claim "holds ~a dozen hand-written structural patterns with **no dates, actors, or outcomes**" is factually wrong on two of three counts: `UPSET_DATABASE` entries carry `year` (a date), `region`, and `actual_outcome` — the file literally stores "what happened next" for ~a dozen cases. The accurate gap is different and still sufficient: those entries are election-upsets only, matched by keyword overlap (`UpsetPatternMatcher`), with no typed actors, no corporate-incident structure (trigger_type, constraint_types, escalation, tempo, exit_authority), and no excerpt-anchored provenance. As written, a fresh reader inherits a false belief about the codebase. *Recommendation:* rewrite the sentence to the accurate characterization.

**M10 — 🟡 The spec violates its own circular-validation pre-commitment while finalizing the scoring design.**
*Scope:* lines 129–130 (Open Questions), 393–397 (WEIGHTS finalized), 419–447 (worked example), 583–589 (Risk 2).
*Finding:* The doc requires "the 30 titles … fixed in writing **before any scoring design is finalized**" and admits "the corpus curator designed the schema around the Nvidia case." Yet the document's status is **Approved** with weights v1, the 0.45 threshold, tiers, and the Nvidia worked example all final, and no corpus list is committed anywhere in the doc or the plan. The discipline the design prescribes for itself has already been breached by the design. *Recommendation:* either attach the 30-title list to this document and mark the scoring section provisional pending the leave-one-out calibration, or demote the doc's status from Approved.

**M11 — 🟡 The spec's declared authority chain resolves to files/rules that do not exist.**
*Scope:* lines 605–606, 421, 41–42, 88–92.
*Finding:* `concepts_brief.md` is cited as "authoritative source for schema, weights, tag rules, token math" — `docs/` contains only this file; the pointer is dead. Line 421's "Exact-string matching after the stated canonicalization rule" references a rule stated nowhere in the document (presumably in the missing brief). Consequently the two anchor numbers — ~2.3k tokens per fresh incident and ~16.5k–66.8k per debate question — have no derivation anywhere in the tree. The standard requires a fresh reader to confirm risks and trade-offs from the spec itself. *Recommendation:* inline the canonicalization rule, the token math, and whatever of the brief is still operative, or commit the brief alongside this document.

**M12 — 🟡 Multi-tenant corpus governance is unaddressed.**
*Scope:* lines 556–559 (Security NFR), 296–299, 171–176 (CUJ 4); repo `api/server.py:1–7`.
*Finding:* The server's documented posture is public multi-user SaaS (per-request `X-API-Key`, "multi-user safety"), and the incident routes reuse exactly that key handling — yet the design adds a shared, mutable, user-content corpus: any key holder's paste can enter provisional records and `_raw/`, become matchable context for every other user, and persist indefinitely (no retention policy for the spool). Threats unanalyzed: cross-user content exposure, adversarial corpus poisoning by a single account (Risk 1 covers model error only), single-human curator throughput. "The corpus is not published" addresses publishing, not tenancy. *Recommendation:* state the tenancy model explicitly; if multi-user, add per-user record ownership on provisional records, curator-only promotion, and spool retention limits to the Security NFR.

**M13 — 🟡 User edits to extracted fields can never affect matching — CUJ 1 implies otherwise.**
*Scope:* lines 140–149 (CUJ 1) vs. 321–322 (data flow), 296–297 (cache); plan file 26.
*Finding:* CUJ 1 has the user "confirm the extracted fields in the review state" and then shows "the confirmed card, top-5 matches …" — but the data flow states "confirm/edit state governs SAVING only; matching runs on the in-memory card," i.e., the pre-edit card. There is no re-score-on-edit path (no endpoint, and the repeat cache would return the pre-edit result on resubmission of the same paste). A user who corrects a wrong `trigger_type` sees matches computed from the error they just fixed, and cannot ever see corrected matches. *Recommendation:* either make confirm trigger a re-match with the edited card (and bypass/refresh the cache on edit), or reword CUJ 1 to say matches reflect the extracted card as-is.

## Nits

**N1 — 🟢** Line 576: "Known Risks (**the three weakest points**)" introduces four items (578–601). Update the count.
**N2 — 🟢** Line 446: "see the provenance section of the anchor case **below**" — the anchor-case section is above (lines 50–73). Fix the direction.
**N3 — 🟢** G3 (85–87) requires a stored timeline per match (up to 5 + pasted); CUJ 1 (143–144) renders "both timelines." Harmonize wording ("the pasted incident's and each match's").
**N4 — 🟢** Alternatives C/D/E/I reject "by author" (481, 492, 502, 540). Per the standard, rejection rationale should stand on the technical trade-off alone; the trade-offs are mostly present — delete the person-attribution phrasing.
**N5 — 🟢** Rollback wording (572–573): "flip the flag back" — after removing the dispatch-table entries the flag check is gone too; rollback actually restores *ungated, always-on* debate, a behavior change worth stating.
**N6 — 🟢** G4's ≤~2.3k budget ignores the repair-retry path (a second full call doubles usage and would fail CUJ 1's token assertion on retry); no input/output derivation is shown (4k chars ≈ 1k tokens + schema prompt + card output plausibly exceeds 2.3k).
**N7 — 🟢** Base-rate denominator ambiguity (407–411): "over the strong tier" vs the example's corpus-wide "4 of 30" rendering (which only fits the trigger_type fallback). State which denominator the rendered counts use in each case.
**N8 — 🟢** Tag-cascade rule 2 (267–269) is unreachable in v1: no UI or API step attaches a primary document to a paste (UI flow and plan file 25 include no attachment step), so `documented` can arise only from hand-authored curated records. Harmless, but present rule 2 as v2-only or note it.
**N9 — 🟢** `retrieval_debug` (260, 335, plan 21/28) is a required response field whose contents are never defined (top-20 list? per-component contributions? distances?). Define the shape.
**N10 — 🟢** Extraction output-token budget unspecified (317–320): `AsyncGroqLLMClient.chat` defaults to `max_tokens=2048` (`config.py:36`); a full 20-field card with claims + timeline risks truncation, and the "tolerant-parse fallback" would silently convert truncation into a thin card and a weaker silence line. Pin `max_tokens` (and the truncation-detection behavior).

## Standard Compliance Summary

* **Alternatives Rule:** satisfied — ten alternatives with pros/cons/rejections (attribution phrasing per N4).
* **Risks & Limits:** satisfied structurally (four risks with partial mitigations), but M12's tenancy gap and M5's overstated payoff show the risk list is incomplete on its own feature's terms.
* **Problem/Goals/Non-Goals/Architecture:** present; the failures are factual accuracy (M9), internal consistency (M2, M3, M10, M13), and specified-mechanics gaps for deterministic, load-bearing components (M4–M8) — the doc repeatedly promises mechanical, auditable behavior while leaving the mechanics of those components undefined.

## Verdict for the Orchestrator

**No Blockers; 13 Majors, 10 Nits.** The architecture is coherent and the repo-claim accuracy is unusually high (10+ verified claims), but the spec currently fails the standard's core principle for a fresh reader: several load-bearing mechanisms (`corpus_version`, `outcome-Jaccard` inputs, `summary_embed` fields, curated-first semantics, the mode gate, the canonicalization rule) are named but not defined, two CUJs assert behavior the mechanism cannot produce, and the research loop's dependency contract (M1) mismatches the actual `search/web.py` API. **M1 and M13 must be resolved before Phase 1 planning; M1's search contract before Phase 4; the definitional gaps (M4–M8) before the scoring phase.** Recommend a revision round rather than implementation start.

---

## Reviewer 2: egm-structural (Structural Reviewer)

# Structural Review — `docs/designs/incident-memory.md`, Stage 7 Round 1

**Scope audited:** lines 1–625 (spec proper; the `## Detailed Implementation Plan` section from line 626 was read only to check for spec/plan contradictions). **Standard applied:** `feature-spec-standard.md`. **Method:** full read of the target scope; repository claims verified by reading the cited modules (`core/upset_patterns.py`, `rag/hybrid_retriever.py`, `rag/builder.py`, `Dockerfile`, `main.py`, `api/server.py`, `api/index.py`, `search/web.py`, `core/llm_client.py`, `agents/config.py`, `concepts_brief.md`).

## Structural conformance summary

- All five areas the standard requires are present and correctly ordered: Problem Statement (`## The Problem`), Goals & Non-Goals, Proposed Architecture (`## Technical Plan (Architecture)`), Alternatives Considered (A–J, each with pros/cons/rejection rationale — strong Alternatives-Rule compliance), Risks & Mitigations (NFRs + `## Known Risks`).
- Heading hierarchy is clean within scope: H1 → H2 → H3, no skipped levels; the four CUJ H3s and the ten Alternative H3s nest correctly. Tables (lines 427–438) and fenced blocks are well-formed; no broken Markdown found.

**Repo claims verified accurate** (no finding): `hybrid_retriever.py` does convert cosine distances with the L2-style formula `1/(1+d)` while `rag/builder.py:85` creates collections with `hnsw:space='cosine'` — the doc's "bug this design does not inherit" claim (line 290) is true; `api/server.py:85` has the hardcoded `/api/analyze` comparison and the `X-API-Key` handling (lines 90–99); `main.py:223–233` has the `run_web` RAG auto-build gated on `chroma.sqlite3` absence; `search/web.py:38` defines `search_news`; `allam-2-7b` is in the repo's known-good model chain (`core/llm_client.py:33`); the agent roster is 10 debate agents (`agents/config.py:1–33`); `EnhancedDebateCoordinator` import matches (`main.py:29`); the Dockerfile currently has no `FASTEMBED_CACHE_PATH`, matching the doc's planned-change framing; `rag/builder.py:3` carries the stale `veritas` docstring.

**No 🔴 Blocker findings.** The document is structurally complete and largely self-consistent. Nine 🟡 Major findings follow; the rest are 🟢 Nits.

---

## 🟡 Major findings

**M1 — Loop-size contract contradicts itself (3–5 questions vs. up to 10).**
*Scope:* Overview line 19; CUJ 1 lines 146–147 vs. G4 lines 89–92, data flow line 328, config line 370, lines 383–384, NFR lines 561–567.
Overview and CUJ 1 state the journey "raises 3–5 research questions" — a total with an implied floor of 3. Everywhere else the arithmetic is two rounds × `questions_per_round` (5) = "up to ten Tavily searches" (lines 383–384, 567, 131–132), and the detector-driven loop can legitimately raise zero questions (no gaps) or up to 5 per round. CUJ 1 is the acceptance-criteria text; as written it asserts a different budget than G4. Reconcile: state the per-round cap, the ≤10 total, and drop the implied floor of 3.

**M2 — CUJ 1's confirm step contradicts the data flow's confirm semantics.**
*Scope:* CUJ 1 lines 140–141 vs. data flow lines 320–322.
CUJ 1's When clause gates the match output on the user "confirm[ing] the extracted fields in the review state"; the data flow states "confirm/edit state governs SAVING only; matching runs on the in-memory card." Both cannot hold: either the response precedes confirm (and CUJ 1's trigger is wrong) or confirm gates matching (and the data-flow statement is wrong). Related under-specification: the loop writes research answers into the in-memory card before the response (lines 256–257, 330), but the spec never says how those write-backs interact with user edits made afterward in the review state — which version is saved, and does a user edit of a research-filled field invalidate the write-back?

**M3 — Outcome write path contradicts Known Risk 1's "curated 30 are safe."**
*Scope:* CUJ 3 lines 165–168; outcome path lines 337–338 vs. Known Risk 1 lines 578–582.
Risk 1 asserts the curated records are safe because they are hand-authored, while auto-extracted provisional records carry model error. But the outcome path writes model-extracted outcome fields directly into the JSON record — including curated records — with no review/confirm step (contrast the paste path's confirm-before-save). Model error can therefore corrupt exactly the records Risk 1 declares safe. The risk register and the design disagree; either add a confirm/review step (or provisional-outcome with revert) to the outcome path, or amend Risk 1.

**M4 — Problem statement mischaracterizes `core/upset_patterns.py`.**
*Scope:* The Problem, gap 1, lines 33–36.
The claim "no dates, actors, or outcomes" is false against the repo: every `UpsetEntry` carries `year`, named actors, `consensus_prediction`, and `actual_outcome` (`core/upset_patterns.py:50–77`, entries at 84–402), and the matcher returns matched cases with "what happened" attached. The defensible gap is different: keyword-scored matching (not structural), election/geopolitics-only content, top-3 output, hard-coded with no user growth path, no typed fields comparable to the incident schema. The conclusion ("no incident memory") survives, but the supporting facts are verifiably wrong, which undermines the problem statement for any reader who checks the repo.

**M5 — The research loop's only search dependency hard-filters results to the last 24 hours.**
*Scope:* Integration points lines 381–384 (claim of unchanged, as-is use) vs. `search/web.py:49–68`.
`search_news()` unconditionally applies `from_date = now − 24h`. The spec treats it as a drop-in ("the repo's existing Tavily integration is the research loop's only search dependency") and G7 promises gap closure via search — but expected-evidence gaps pointing at artifacts even days old (a filed 8-K, a board statement earlier in the week — the anchor case's own 8-K is 5 days old at document date) will return nothing and surface as "no source available" for a reason the spec never names. The spec must either note/override the date filter for the research path or scope which gap types can realistically close.

**M6 — `retrieval_debug` is a load-bearing response element that is never defined.**
*Scope:* CUJ 1 line 148; data flow line 335 (plan assertions depend on it: lines 813, 927).
The term appears as a contract element of every match response, including in test assertions, but no section defines its contents or shape. The audit story (per-component contributions, `WEIGHTS_VERSION` echo, lines 393–397) implies what belongs in it, but the contract is never stated — a fresh engineer cannot implement or test it from this document.

**M7 — `corpus_version` is an undefined cache-key component.**
*Scope:* Data stores line 296–297; data flow line 314.
The repeat cache is keyed on `(sha256(paste), corpus_version)`, but nothing defines what `corpus_version` is, how it is computed, or when it changes (promote/prune? outcome writes? any hand edit of a JSON file?). Since the corpus is explicitly mutable by hand edits (lines 294–295), cache invalidation semantics are load-bearing for both correctness (stale matches) and the "0 tokens and 0 searches on a repeat paste" guarantee (lines 90–92). Define the bump rule or the invalidation contract.

**M8 — G8's "reserved for forecast questions only" has no enforcement mechanism and clashes with "behaves exactly as today."**
*Scope:* G8 lines 103–105; Non-Goals lines 113–115; API changes lines 351–355; Alternative H lines 523–533.
Line 353–354 says the flag-on path "behaves exactly as today … and serves forecast questions only" — but today's `/api/analyze` accepts any question type, the LLM-classifier router was rejected (Alternative H), and the structural gate only pre-selects a visible selector with a one-click override. Nothing in the design restricts the debate pipeline to forecast questions. Either reword G8/Non-Goals as a default-routing policy or define the restriction.

**M9 — The circular-validation guard is violated by the document's own finalized state.**
*Scope:* Open Questions lines 128–130; Known Risk 2 lines 587–589; finalized scoring at lines 393–397, 403–411, 419–447; Status line 4.
Open Questions and Risk 2 require the 30-title corpus list to be committed "before any scoring design is finalized." This Approved document *is* the finalized scoring design (nine-component weights, 0.45 threshold, named fixtures), while the list is not committed anywhere in it (`data/incidents/README.md` is future work, plan file 13) and the doc never states whether the precondition has been met. Note the asymmetry: the threshold is explicitly provisional ("a stated guess," line 128), but the weights are not. State the corpus list's commit status, commit it, or mark the weights provisional pending the committed corpus — otherwise the doc's own mitigation is retroactively unsatisfiable.

---

## 🟢 Nit findings

1. **Count mismatch in a heading** — line 576: `## Known Risks (the three weakest points)` introduces four numbered items (578, 583, 590, 595). Fix the heading or the count.
2. **Section header overclaims** — line 365: "Integration points (existing code, unchanged behavior)" lists four items that are modifications: `config.py` new keys (367–370), `rag/builder.py` gaining `build_incidents()` (371–373), Dockerfile cache copy (374–376), and Web UI changes (385–389).
3. **Config-key naming asymmetry** — lines 368–369: `incidents_data_path` / `incidents_collection` (plural) vs. `incident_weak_threshold` (singular).
4. **Wrong-direction internal pointer** — line 447: "see the provenance section of the anchor case *below*" — that section is above, at lines 50–73.
5. **Revision residue** — line 402: "the former optional gloss is cut" references an artifact that no longer exists anywhere in this document; a fresh reader has nothing to attach it to.
6. **Diagram label ambiguity** — line 308: the forecast branch is labeled "(flag on)", yet the box beneath (311–313) handles both flag states.
7. **Worked example depends on unstated vocabularies** — line 421 appeals to "the stated canonicalization rule," which is never stated; `actor_roles` is "CLOSED vocabulary in a constants module" (220–221) but its values are never enumerated, even though the 0.15-weight Jaccard and the fixture arithmetic (431) use specific values.
8. **Fixture inconsistency in the worked example** — line 437: Petraeus's outcome row reads "none recorded yet," but the data-store contract says the 30 curated records have outcomes pre-filled (285–287), and Petraeus 2012 is a settled case by the doc's own definition.
9. **`data/incidents/` root mixes record JSONs, `sources/` dirs, and `_raw/` spool** (211, 251–252, 298–299) while `rebuild_index()` "read[s] all JSON files" (291–292); the exclusion of `_raw/` (and its unspecified spool file format) from the rebuild glob is never stated.
10. **`as of <date>` semantics undefined** (18, 80, 145, 335): query time, corpus freshness, or something else is never pinned — including what a cached repeat-paste response (296–297) stamps.
11. **Authoritative-source pointer carries pre-redesign language** — lines 605–606 delegate schema/weights/tag rules/token math to `concepts_brief.md`, which still describes the optional narrative gloss and debate-as-second-path (`concepts_brief.md:14–20`) that this doc cuts (line 402) or parks (G8). Scope the authority per topic or bump the brief.
12. **Rollback wording slip** — line 572: "(and flip the flag back)" — the flag defaults off and is not part of the rollback path.
13. **Headline token budget is asserted, not derived** — lines 88–92, 565–569: the ≤ ~2.3k figure's arithmetic lives only in `concepts_brief.md` (computed before the gloss cut); given the extraction prompt must carry a ≤4,000-char paste plus the full typed schema, state the input/output split in-doc (the E2E token audit is the only existing check).
14. **G2 overgeneralization** — lines 81–84: "exactly one provenance tag … with its source" — `inferred` claims carry `supports` claim ids rather than a source, and `speculative` claims may carry none.

**Conclusion:** No blockers. The document satisfies the feature-spec standard's mandatory sections and the Alternatives Rule well. The nine Major findings cluster into three themes that should be resolved before implementation: (a) numeric/sequence contradictions inside the acceptance-criteria text (M1, M2) and between the risk register and the design (M3, M9); (b) undefined load-bearing contract terms (M6, M7); and (c) repo-reality claims that verification falsifies or complicates (M4, M5, M8).

---

## Reviewer 3: egm-style (Technical Copy Editor)

# Style Review — Stage 7 (Critic Review, Round 1)

**Reviewer:** egm-style (Technical Copy Editor)
**Target:** `/home/rushi/vg/docs/designs/incident-memory.md`, lines 1–625 (spec range; plan consulted only to check cross-references and wording contradictions)
**Method:** full read of the audited range; in-repo verification of every claim about existing code in that range; arithmetic checks on all stated numbers. No context files were supplied; the review is self-contained.

No 🔴 Blockers found. Twelve 🟡 Major findings, then 🟢 Nits.

---

## 🟡 Major findings

**M1. Uncalibrated claim about existing code in Gap 1 — `CALIBRATE`**
*Scope:* The Problem, gap 1, lines 33–36.
*"…`core/upset_patterns.py` holds ~a dozen hand-written structural patterns with no dates, actors, or outcomes…"* The count is right (11 entries), but the file holds 11 `UpsetEntry` **case records**, each carrying a `year` and an `actual_outcome`; only the `actors` part is true. "Structural patterns" also mislabels the entries (the ~14 pattern labels are constants the entries reference). A reader who opens the file falsifies two of the three claimed absences. The real gap (no structured actor fields, no per-claim provenance, keyword-overlap matching that cannot rank structural similarity) survives recalibration: e.g., "holds ~a dozen hand-written case entries keyed to coarse pattern labels — a single year and a prose outcome each, no actor structure, no excerpt-anchored claims."

**M2. "Nothing existing breaks on deploy" contradicts the document's own changes — `CALIBRATE`**
*Scope:* Non-Functional Requirements, Rollout & Rollback, lines 570–574.
*"…the feature is additive … with the debate flag defaulting off so nothing existing breaks on deploy."* Two documented changes break existing behavior: (a) `/api/analyze` stops running the debate for existing users when the flag is off (typed `debate_disabled`, lines 351–353); (b) Step 0 deletes `cli.py`, `vg-main/`, `testapp/`, root test files, and strips CLI handling from `main.py`, and the README "drops CLI invocations" (lines 641–678). Recalibrate to: the incidents routes are additive; the flag-off `debate_disabled` response and the Step 0 tree cleanup are deliberate behavior changes, named as such.

**M3. Absolute stop-rule wording omits its own two-round cap — `CALIBRATE`**
*Scope:* G7, lines 101–102.
*"the loop stops only when nothing further can be closed with available sources — never on a model's judgement."* The same sentence grants "maximum two rounds," and the plan's stop rule is the three-way disjunction (nothing closable / all remaining gaps no-source / two rounds elapsed; plan lines 916–919). "Only when" states one disjunct as the sole condition. Rewrite: "the loop stops when nothing further can be closed with available sources, every remaining open gap has returned 'no source available', or the two-round cap is reached — never on a model's judgment."

**M4. "Same story" dedupe claim outruns the byte-identical mechanism — `CALIBRATE`**
*Scope:* CUJ 4, line 176; mechanism defined at lines 296–297.
*"paste-hash dedupe prevents the same story from entering twice."* The named mechanism is keyed on `(sha256(paste), corpus_version)` and returns cached results for **byte-identical** re-pastes; a re-worded version of the same story is not caught, and the spec never states that the cache blocks the provisional save path (only that it returns cached results). Narrow the claim to byte-identical re-paste, and state what (if anything) stops a re-worded duplicate from being saved.

**M5. Wrong-direction cross-reference**
*Scope:* Worked example, lines 446–447.
*"(see the provenance section of the anchor case below)"* — the anchor-case provenance section is **above** (lines 50–73); nothing on that topic follows. Replace "below" with "above" or drop the direction.

**M6. Dangling reference: "the stated canonicalization rule"**
*Scope:* Worked example, line 421.
*"Exact-string matching after the stated canonicalization rule…"* No canonicalization rule is stated anywhere in the document. The nearest candidate is the `actors` field comment ("people by common name, orgs by short name", line 219). Since this paragraph is the stated basis for the golden scoring fixtures, the rule must be stated inline or referenced precisely.

**M7. Provenance wording drift on the anchor record — `CALIBRATE`**
*Scope:* lines 52 ("The Nvidia case is **documented**"), 446 ("a documented record"), 588–589 ("its tag status is settled (documented)").
These three statements read as if the record is uniformly `documented`, contradicting the explicit tag split (lines 59–65) under which the affairs, the intelligence assessment, and the 13% share drop are `reported_unconfirmed`, and contradicting G2's per-claim tagging. Standardize on one formulation, e.g. "the record's tag assignments are settled: the resignation and appointments are `documented`; the remaining claims are `reported_unconfirmed`."

**M8. Non-Goals wording contradicts G8 — leftover from the pre-redesign framing**
*Scope:* Non-Goals, lines 113–115 (vs Overview lines 21–22, G8 lines 103–105).
*"Replacing or shrinking the 10-agent debate inside incident mode: it is parked behind a flag…"* As written, this says the debate stays *inside* incident mode, while G8 and the Overview say it is "out of the incident path entirely." The "inside incident mode" qualifier is stale. Rewrite: "Replacing or shrinking the 10-agent debate pipeline: it is kept intact and parked behind a flag (default off) for forecast questions only."

**M9. The "mechanical" tag cascade is ambiguous at its decision boundaries**
*Scope:* Claim tagging — precedence cascade, lines 264–273.
Three problems a mechanical rule cannot have: (1) rule 2's "primary source directly cited in the paste" is undefined at claim level vs paste level; (2) rule 3's "No primary document" is undefined when a primary source is cited but the document is not attached with its excerpt stored; (3) as ordered, rule 4 (`inferred`) is unreachable for the claims it describes — a conclusion drawn from other claims with no primary document is captured by rule 3 (`reported_unconfirmed`) first, so `inferred` + `supports` fires only in a narrow, unstated case. State the decision procedure unambiguously (what each condition is evaluated against, per claim, and the actual precedence).

**M10. Ambiguous, self-disclaiming provenance sentence — `CALIBRATE`**
*Scope:* Provenance status of the anchor case, lines 70–71.
*"A classified intelligence assessment can never reach `documented` — that note is UI copy, not an ingest rule."* "That note" can be misread as the intelligence assessment itself, and the absolute "never" is immediately disclaimed as unenforced — the reader cannot tell what the tagger actually does (the cascade keys on document attachment, not content type). Recalibrate: state the mechanical fact first ("the cascade has no content-type rule; `documented` is reachable only via an attached, stored excerpt"), then the display guidance.

**M11. Heading/list count mismatch**
*Scope:* Known Risks, lines 576–601.
The heading says "the three weakest points"; the section numbers **four** risks. Fix the heading ("the four weakest points") or drop the parenthetical.

**M12. "3–5 research questions" states a floor the mechanics cannot guarantee — `CALIBRATE`**
*Scope:* Overview line 19; CUJ 1 line 145.
*"It then raises 3–5 research questions…"* / *"3–5 research questions were raised only from mechanical gap detectors…"* The detectors emit one question per detected gap, capped at `questions_per_round` (5); nothing guarantees a minimum of three, and a fully-filled, contradiction-free paste that matches the corpus yields zero questions and zero searches. Recalibrate to "up to five — one per detected gap, ranked and capped."

---

## 🟢 Nit findings

**N1. File-count drift.** Header revision note says "six-file package" (lines 6–7); the layout says "six logic files plus a package marker" (line 184) — seven files. Align ("six logic files plus a package marker" everywhere).

**N2. Terminology & format consistency bundle** (pick one form each):
- "why-it-matches" (lines 17, 79) vs "why-matches" (lines 198, 398) vs "why/breaks bullets" (lines 143, 325).
- "`outcomeJ` term" (line 590) vs "outcome-Jaccard" (line 396) / "typed outcome term" (line 94).
- "NVIDIA" (line 39) vs "Nvidia" (lines 52, 424, 446).
- "≤4,000 characters" (line 77) vs "≤4k chars" (line 304) vs "4,000-character" (plan line 849).
- "≥30 curated records" (line 138–139) vs "the 30 curated records" everywhere else (lines 128, 286, 445, 587; file 14 "× 30").

**N3. Spelling variant.** "judgement" (line 102; also plan line 919) against otherwise-American spelling ("behavior", lines 353, 365). Use "judgment" or note the house style.

**N4. Dangling draft reference.** "the former optional gloss is cut" (line 402) — the gloss does not exist in this document; a fresh reader meets an undefined "former" element. Either define it inline ("an optional LLM narrative gloss over the score, dropped in this revision") or let the plan's cuts section carry it alone.

**N5. Decorative adverbs / ungrounded superlatives in Alternatives.** "genuinely need" (line 499), "routes frictionlessly" (line 525), "The most widely documented local embedding stack" (line 515). Drop "genuinely"/"frictionlessly"; ground or soften "most widely documented."

**N6. Decorative adjective.** "a clean 501" (line 357) → "an explicit 501."

**N7. Figurative self-reference.** "That result is the demo working … instead of flattering the analogy" (lines 440–442). Restate plainly: "the correct outcome: a genuinely partial match reported as weak, not inflated."

**N8. Grammar.** "The templated questions also read stiff" (line 600) → "read as stiff."

**N9. Undefined tag ordering.** "claims tagged below `documented`" (line 413) implies a ranking never defined; the tags are an unordered enum (line 82). Use "any tag other than `documented`."

**N10. Undefined one-off term.** "the corpus frequency of the structural signature" (line 408) — "structural signature" appears only here. Define or reuse "structural pattern."

**N11. Undefined term.** "Steady-state cost" (line 88) — steady vs non-steady state is never distinguished; "per fresh incident" already carries the meaning. Drop "steady-state."

**N12. Self-softening absolute.** "a hard ceiling" (line 278) is excepted two sentences later ("reaches `documented` only if the user later attaches", lines 279–281). Say "a ceiling at loop time."

**N13. Scope qualifier dropped.** Line 276: "claims the user *cannot* source" omits the "conclusion-changing" qualifier used at lines 109–110 and 612–613, silently broadening the post-v1 verification scope. Restore the qualifier.

**N14. Stamp-scope drift.** Overview line 18 and CUJ 1 lines 144–145 attach "all stamped 'as of <date>'" to different item sets, while the response carries a single response-level `as_of` (lines 205, 334–335). State once that the stamp is response-level.

**N15. Self-referential pointer.** "…a one-line migration plus reindex and is called out as such" (lines 573–574) reads as a pointer to another callout; this sentence is the callout. Rewrite: "note: an enum rename requires a one-line migration plus reindex."

**N16. Resource-list inaccuracy.** "Repo modules cited in the Technical Plan" (lines 605–608) lists `core/debate.py`, which the Technical Plan never cites by path; it names `EnhancedDebateCoordinator` (line 353), which lives in `vg/core/enhanced_debate.py`. Either cite that path at line 353 or correct the list.

**N17. Unexplained figure.** "~16.5k–66.8k tokens per question" (line 41) — the endpoints (converged shadow path vs full debate) are unstated, and the designated source (concepts_brief.md token math, line 605) is not pointed to at the claim. Add one clause of either.

**N18. Arithmetic looseness.** "should cost an order of magnitude less" (line 42): 16.5k → ~2.3k is ~7×, under one order of magnitude. Quantify ("~7–29× less") or soften ("a fraction of").

**N19. Stale spec wording vs plan.** "CLOSED vocabulary in a constants module" (line 220) — the plan folds the constants module into `schema.py` (file 11) and the cuts section removes `constants.py` outright (lines 948–951). Update the spec comment to point at `schema.py`.

**N20. Under-specified term the design depends on.** `summary_embed` "fixed Python template over canonical fields" (line 247) — the canonical field set is never enumerated; CUJ 3's "no re-embed occurs" (line 168) only holds because outcome fields are excluded (stated only in plan file 27). Say so in the spec.

**N21. Spec/plan hedge mismatch.** "on server start (and optionally per query against top-20 candidates)" (line 293) vs the plan's unconditional "count/hash drift check at server start and per query against top-20 candidates" (plan lines 722–724). Remove "optionally" or make the plan conditional.

---

## Claim-calibration checks that passed (not reported as findings)

Verified against the repo and confirmed accurate — no action needed: `UPSET_DATABASE` holds ~a dozen entries (count only); `rag/builder.py` creates collections with `hnsw:space='cosine'` while `rag/hybrid_retriever.py` applies the L2-style `1/(1+d)` transform (the "bug this design does not inherit"); `do_POST` hardcodes the `/api/analyze` comparison and the `X-API-Key` handling exists; `EnhancedDebateCoordinator` exists (`vg/core/enhanced_debate.py`); `core/llm_client.py` recreates loop-bound limiter state and `api/server.py` calls `asyncio.run` per request (the noted pre-existing bug); `search_news()` exists and the debate pipeline's first act is a Tavily call (`search_news` precedes the cache check in `run_full_pipeline`); `BAAI/bge-small-en-v1.5` is the repo's embedding model and the Docker build pre-bakes it; `config.py` uses the env-var pattern and `model_small` is `allam-2-7b`; the current verdict panel is a 350px-wide `.app-side`; `data/incidents/` does not exist in the tree (matching the "designated but not committed" claims); upset-pattern injection into debate context is real (via `contrarian_engine` → Oracle Mode), so Alternative D's Pros line stands. The weights sum to 1.0 and the worked-example arithmetic (0.138 + 0.20 + 0.021 + 0 + 0.025 + 0.05 = ≈0.43, weak against the 0.45 threshold) is internally consistent.

**Summary:** 0 Blocker, 12 Major, 20 Nit. The recurring pattern is revision residue: statements carried over from the pre-redesign framing (M8, M11, N4, N19) and absolute phrasing that the document's own mechanics disprove (M2, M3, M4, M12). All Majors are one-to-three-sentence fixes; none requires structural change.
