# Comprehension Report — Stage 6 (Comprehension Test)

**Target:** `/home/rushi/vg/docs/designs/incident-memory.md` (FeatureRange 1..625; DetailedRange 626..1010)
**Reviewer:** `egm-comprehension` — self-containment test, document-only read (no repo access, no GoldfishContext)
**Preset:** Consolidated report with all review rubrics (uninterrupted full flow)
**Date:** 2026-11-18

---

# Comprehension Test — SELF-CONTAINMENT
Target: `docs/designs/incident-memory.md` (FeatureRange 1–625; DetailedRange 626–1010). Read scope: document only. Mode: REVIEW. No 🔴 Blockers — every section was paraphrasable; the findings below are places where a fresh reader must guess.

## What this proposes
The document proposes adding "incident mode" to the VG web app: the user pastes a live news incident (English, ≤4,000 chars); one small-model extraction call (allam-2-7b via Groq) produces a typed incident card in which every claim carries a provenance tag; the card is structurally scored against a curated corpus of ~30 hand-authored historical incident records (JSON source of truth, rebuildable Chroma index, local fastembed embeddings) to return the top-5 matches in strong/weak/no-match tiers with mechanically generated why-it-matches/where-it-breaks bullets, a base rate, and a silence line, all stamped "as of <date>". A grounded research loop then raises templated questions only from four mechanical gap detectors, runs exactly one Tavily search per question (max two rounds, ≤10 searches), writes tagged answers back through existing card fields, and re-scores — no model decisions anywhere in the loop. The corpus grows from use (confirmed pastes saved as provisional records, curated via promote/prune) and manual "what happened next" outcome recording feeds a fixed 0.05 outcome term in scoring. The existing 10-agent debate pipeline is kept but parked behind a `debate_enabled` flag (default off) for forecast questions only; incident mode constructs zero agents and is built as a six-file `incidents/` package sharing only three imports with the repo. Delivery is Step 0 (delete duplicate app copies/orphan tests to make the tree single-copy) plus four phases (schema, scoring, endpoint+panel, gap loop) across 34 target files, verified offline.

## How the existing system works, per this document
Per the document, VG today is a web-served Python app (entry points `analyze_async`/`analyze`/`run_web` in root `main.py`, HTTP server in `api/server.py` with a hardcoded `/api/analyze` route, Vercel handler `api/index.py`, UI in `api/static/`) that answers questions through a 10-agent debate pipeline (`EnhancedDebateCoordinator`) costing ~16.5k–66.8k tokens per question; it has no store of real incidents — `core/upset_patterns.py` holds ~a dozen hand-written structural patterns and a RAG layer holds wisdom prose. The repo already ships everything incident mode reuses: fastembed with `BAAI/bge-small-en-v1.5` (~130 MB cache pre-baked in Docker), ChromaDB at `./chroma_db` (whose `hybrid_retriever.py` converts cosine distances as if L2 — a bug the design does not inherit), a Groq client (`core/llm_client.py`, shared RPM limiter with a known per-request `asyncio.run()` bug), Tavily search (`search/web.py` `search_news`), env-var config, `X-API-Key` handling, and Docker pre-baked wisdom collections. A prior "web-only build" landed on a divergent copy (`vg-main/`, `testapp/`, root `cli.py`, orphan root tests), which Step 0 exists to reconcile into a single tree.

## Findings

### 🟡 Major

1. **Severity**: 🟡 Major. **Scope**: G5 (l.93), CUJ 4 (l.175), Risk 1 (l.581) — term "curated-first matching". **Discrepancy**: The term is used three times as a design property but never defined. A fresh reader cannot tell whether provisional records participate in matching/scoring/base-rate counts before promotion, or only curated records match until promotion. Behaviorally significant either way, and Risk 1 cites it as a mitigation for poisoned provisional records, which requires the exclusion reading.

2. **Severity**: 🟡 Major. **Scope**: Overview (l.19), CUJ 1 (l.145), data flow (l.328), file 30 (l.894–905). **Discrepancy**: "Raises 3–5 research questions" is asserted repeatedly, but the mechanism only ever specifies a cap (`questions_per_round` = 5) — nothing produces a floor of 3, and a complete card with zero gaps could legitimately raise zero questions. The reader cannot reconcile the asserted 3–5 range with detector-driven counts.

3. **Severity**: 🟡 Major. **Scope**: "as of <date>" stamp — l.18, G1 (l.80), CUJ 1 (l.145), silence line "dated" (l.414), file 21 (l.814). **Discrepancy**: The stamp is a headline honesty feature ("as-of dating" is in the revision note), but the document never says which date it is: query time, latest `recorded_at` in the corpus, or something else. Two readers can implement different semantics.

4. **Severity**: 🟡 Major. **Scope**: Data stores (l.296–297) — `corpus_version`. **Discrepancy**: The repeat cache is keyed on `(sha256(paste), corpus_version)`, but `corpus_version` is never defined (a config value? corpus record count? corpus hash?) and is not among the six new config keys. The "0 tokens/0 searches on repeat paste" guarantee depends on how it changes, and the reader cannot tell.

5. **Severity**: 🟡 Major. **Scope**: Scoring weights (l.393–397), worked example (l.427–437), schema (l.239–243). **Discrepancy**: Comparison semantics for several components are unstated: "outcome-Jaccard" never says which outcome fields (actors? constraint_types?) feed the Jaccard, and `resolution` is a `list[enum]` with "primary first" whose comparison rule (primary-element equality? list Jaccard?) is never given — the worked example only shows single-element cases. An implementer must invent the arithmetic for two scored components.

6. **Severity**: 🟡 Major. **Scope**: Schema (l.247–248), file 11 (l.714–715), file 27 (l.869) — "canonical fields" of `summary_embed`. **Discrepancy**: The embedding template is "fixed Python template over canonical fields", and a template change forces a full re-embed, but the canonical field list is never enumerated (file 27 only adds that outcome fields are excluded). File 30's "match-relevant set" is a hint, not a definition; the reader must guess what gets embedded.

7. **Severity**: 🟡 Major. **Scope**: Schema (l.220–221), worked example (l.431), files 13–14. **Discrepancy**: `actor_roles` is a "CLOSED vocabulary in a constants module", but the vocabulary values are never enumerated — only seven incidental examples appear in the Petraeus row. Since curated cards are hand-authored (files 13–14, not by this implementation) and scoring depends on exact-string role matching, the closed set is load-bearing and unavailable to the reader or curator.

8. **Severity**: 🟡 Major. **Scope**: CUJ 2 (l.151–162) vs data flow (l.305–315), integration (l.387–388), file 25 (l.848–849), file 22 (l.826–828), cuts (l.967–968). **Discrepancy**: Flag-off debate behavior is described three incompatible ways: (a) file 25 — the Debate option is "inert" (unclickable); (b) CUJ 2 — the Debate option "yields a typed 'debate disabled' response"; (c) CUJ 2 — "incident mode still serves the question from recorded history", while the data flow shows the flag-off `/api/analyze` branch ending at the typed response with no fallback edge to `/api/incident-match`. The reader cannot tell whether the UI disables the option, the server returns only the typed response, or the server automatically falls back to incident matching.

9. **Severity**: 🟡 Major. **Scope**: Explicit cuts (l.967–968). **Discrepancy**: "the panel reads `debate_enabled` from config and renders the Debate option inert... nothing to fetch." Browser-side JS cannot read server config without a fetch or a value baked into the served page; the mechanism is unstated, so the reader cannot tell how this is meant to work.

10. **Severity**: 🟡 Major. **Scope**: File 25 (l.849–850) vs Verification (l.997) and file 21 (l.808). **Discrepancy**: File 25 promises a "4,000-character truncation notice" (implying oversized pastes are truncated client-side), while the verification plan exercises "oversized paste" as a typed failure (implying server-side rejection). Both could coexist (UI truncates, server rejects), but the document never says which is normative.

11. **Severity**: 🟡 Major. **Scope**: CUJ 2 (l.157), data flow (l.305–306), Alternative H (l.529–532), file 21 (l.814–815). **Discrepancy**: The zero-token structural gate lives server-side in `match.py`, yet it "pre-sets a visible mode selector" before submit. How the client obtains the gate's pre-selection (a pre-submit endpoint, a baked-in page value, on-submit dispatch that reroutes) is never stated.

12. **Severity**: 🟡 Major. **Scope**: Tag cascade rule 2 (l.268–269), research ceiling (l.280–281), Risk 4 (l.598–600). **Discrepancy**: "Artifact attachment is the only path to `documented`" — but no UI element or endpoint for attaching artifacts appears anywhere in the file list (files 25/26 list no such control; the cuts list no such endpoint). The reader must assume manual JSON editing, which the document never states.

13. **Severity**: 🟡 Major. **Scope**: CUJ 3 (l.163–169), data flow (l.337–338), file 27. **Discrepancy**: `record_outcome(id, text)` takes a record id, and CUJ 3 says the user pastes "what happened next" text "for it" — but nothing specifies how the user indicates which record (no panel element, no selection flow is listed). The outcome-recording entry point cannot be reconstructed from the document.

14. **Severity**: 🟡 Major. **Scope**: File 31 (l.911–915), file 30 (l.905). **Discrepancy**: The loop's core accept decision rests on "a usable result (URL + usable snippet)" and "the gap's target field filled where derivable" — neither "usable" nor "derivable" is given a mechanical definition, in tension with the design's own discipline that the loop "never [stops/decides] on a model's judgement".

15. **Severity**: 🟡 Major. **Scope**: Component layout (l.184–187), file 10 (l.702–704), file 16 (l.755–761). **Discrepancy**: "Incident mode shares exactly three imports with the rest of the repo — and nothing else", yet `rag/builder.py`'s new `build_incidents()` must embed `summary_embed` — requiring the template (and plausibly the embedder) from `incidents/`, i.e., repo→`incidents` imports beyond the stated three. The direction/scope of the three-import rule is never reconciled with this dependency.

16. **Severity**: 🟡 Major. **Scope**: File 5 (l.671), file 8 (l.689–690), file 10 (l.703), verification (l.973–974), file 18 (l.776). **Discrepancy**: Target files are given as root-relative paths (`main.py`, `api/server.py`, `rag/builder.py`, `incidents/schema.py`) while imports and the smoke test use package paths (`vg.main`, `vg.api.server`, `vg.config`, `vg.rag.builder`). The mapping (repo root itself importable as package `vg`?) is only implied by the `veritas`→`vg` docstring fix and "the existing `tests/` sys.path shim convention" — never stated. A fresh reader cannot be sure where files physically live.

17. **Severity**: 🟡 Major. **Scope**: File 28 (l.878), Verification (l.977) — `VG_CHROMA_PATH`. **Discrepancy**: Tests are specified to redirect Chroma via `VG_CHROMA_PATH`, an env var that is never defined in the document and is not among the new config keys; the doc assumes a pre-existing repo mechanism whose existence a fresh reader cannot verify from the document alone.

18. **Severity**: 🟡 Major. **Scope**: Risk 3 (l.594), file 27 (l.872–873). **Discrepancy**: The triage/freeze trigger — "if no outcomes have been recorded after N weeks of use, freeze the sharpening loop" — leaves `N` as a literal placeholder with no value, and "freeze the sharpening loop" is never defined as a concrete action (stop building features? disable the 0.05 term? hide the outcome prompt?). A fresh reader cannot implement it.

19. **Severity**: 🟡 Major. **Scope**: Data flow (l.335), CUJ 1 (l.148), file 21 (l.813), file 28 (l.879), Alternative B (l.474) — `retrieval_debug`. **Discrepancy**: `retrieval_debug` is a required response field whose tests assert a "shape", but its contents are never specified — and the response composition lists "per-component scores" separately from `retrieval_debug`, so the reader cannot tell what the field holds versus the already-listed scores.

### 🟢 Nit

20. **Severity**: 🟢 Nit. **Scope**: l.446–447. **Discrepancy**: "see the provenance section of the anchor case below" points the wrong way — that section (l.50) is above, not below.

21. **Severity**: 🟢 Nit. **Scope**: l.70–71. **Discrepancy**: "A classified intelligence assessment can never reach `documented` — that note is UI copy, not an ingest rule" has an ambiguous antecedent for "that note" (the preceding sentence? the silence-line wording?), leaving the reader unsure what is UI copy and what is an enforceable rule.

22. **Severity**: 🟢 Nit. **Scope**: File 5 (l.668–672). **Discrepancy**: "Behavior byte-equivalent" mixes file-bytes and behavior phrasing; and the keep-list retains `_consume_option` while deleting all `--cli/--json/--basic` argv handling, with no explanation of why a CLI-named helper survives.

23. **Severity**: 🟢 Nit. **Scope**: Verification (l.981–982); Alternative H (l.532), file 26 (l.863). **Discrepancy**: "record it in a dev-requirements note" doesn't say where; "override logging" never says where overrides are logged.

24. **Severity**: 🟢 Nit. **Scope**: CUJ 4 (l.176) vs l.296. **Discrepancy**: "paste-hash dedupe prevents the same story from entering twice" overstates a byte-exact sha256 mechanism — a reworded duplicate of the same story hashes differently; the document's own cache definition is precise, this phrasing is not.

25. **Severity**: 🟢 Nit. **Scope**: File 21 (l.809). **Discrepancy**: "multi-incident paste → extract the dominant incident or reject" — "dominant" has no stated selection rule, in a design whose ethos is mechanical decisions (safe fallback "reject" bounds the impact).

26. **Severity**: 🟢 Nit. **Scope**: File 26 (l.858); file 21 (l.807); file 30 (l.900–901); schema (l.246). **Discrepancy**: Minor undefined terms: "top-3-equivalent emphasis"; "tolerant-parse fallback" (its sequence relative to the repair retry); how claims are grouped as "same-event" for the contradiction detector (timeline `claim_ids` is a guessable hint, not a rule); allowed values of `sources[].type`.

27. **Severity**: 🟢 Nit. **Scope**: Non-Goals (l.113–115); Alternatives E (l.499–500) vs D (l.486–487). **Discrepancy**: "Replacing or shrinking the 10-agent debate inside incident mode" reads self-tensioned against G8 (the debate is removed from the incident path, not shrunk); and E's "debate questions gain nothing from records" sits awkwardly beside D's premise that debate already gains from historical parallels via `upset_patterns`.

28. **Severity**: 🟢 Nit. **Scope**: Additional Resources (l.604–606). **Discrepancy**: `concepts_brief.md` is declared "authoritative source for schema, weights, tag rules, token math" — exactly the items this document specifies inline — with no statement of which governs on conflict; "post-7-lens-Goldfish review" is undefined process jargon.

29. **Severity**: 🟢 Nit. **Scope**: Data flow (l.323–325) vs scoring (l.403–404); base rate (l.407–408). **Discrepancy**: Whether the displayed top-5 is cut before or after the typed-field rerank of the retrieved top-20 is inferable but not stated; the base-rate fallback is unspecified when the strong tier is empty *and* the paste's `trigger_type` is itself empty.

**No 🔴 Blockers**: all sections were paraphrasable and the overall intent (zero-agent structural incident lookup with a grounded gap loop and a parked debate mode) communicates clearly.
