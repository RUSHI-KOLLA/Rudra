# Incident Memory: Structural Match Against Recorded History

*   **Author:** Rushi
*   **Status:** Draft
*   **Date:** 2026-11-17

--------------------------------------------------------------------------------

## Overview

VG today answers opinion and forecast questions through a 10-agent debate pipeline. It has
no memory of actual events: its historical layers are personality wisdom texts
(Arthashastra, Kissinger) and a fixed, hand-written list of upset patterns — neither records
real incidents with dates, actors, causes, and outcomes. This feature adds a second analysis
mode. The user pastes a live news incident; the system extracts a structured record, embeds
it, and returns the five most structurally similar incidents from a curated corpus of
recorded history — same pattern, not same words — each with why it matches and where it
breaks. Every claim is tagged by provenance with its source. The panel shows how the incident
unfolded and what happened next in the closest match. The corpus grows as a side effect of
use: every pasted incident can be saved as a provisional record with one confirmation, and
recorded outcomes sharpen ranking. Everything runs on the repo's existing free-tier stack:
one small-model extraction call, local fastembed embeddings, ChromaDB, plain Python.

## The Problem

When a live incident breaks, the useful question is not "what would ten personas say" but
"when has this shape happened before, and what happened next?" Three concrete gaps:

1.  **No incident memory.** The repo has no store of real incidents. `core/upset_patterns.py`
    holds ~a dozen hand-written structural patterns with no dates, actors, or outcomes;
    the RAG layer holds wisdom prose. Neither can answer "give me the five closest recorded
    analogs and what followed each."
2.  **No provenance.** LLM output cannot distinguish what a primary document establishes
    from what a reporter attributes from what a model inferred — and for the anchor case
    (NVIDIA, 2026-11-12), the primary 8-K is silent on the resignation's cause, which is
    exactly the fact any narrative would be tempted to paper over.
3.  **Cost without memory.** The debate pipeline spends ~16.5k–66.8k tokens per question.
    A lookup against recorded structure should cost an order of magnitude less.

The solution: a typed incident schema; structural matching by local embeddings plus
typed-field scoring; explanations generated mechanically from field diffs; provenance tags
anchored to stored document excerpts; a one-confirmation growth path for the corpus; and an
outcome-recording loop.

## Goals

*   **G1** — For any pasted incident (English, ≤4,000 characters), return the top-5
    historical matches in strong/weak tiers, each with why-it-matches and where-it-breaks
    bullets generated mechanically from typed-field comparisons.
*   **G2** — Every claim rendered anywhere carries exactly one provenance tag
    (`documented` | `reported_unconfirmed` | `inferred` | `speculative`) with its source;
    `documented` requires the document excerpt in the record, with a load-time downgrade
    to `reported_unconfirmed` if the excerpt file is absent.
*   **G3** — Render two timelines per query: the pasted incident's (extracted at ingest) and
    each match's (stored), with the closest match's recorded outcome appended beneath its
    timeline.
*   **G4** — Steady-state cost ≤ ~2.3k API tokens per fresh incident; 0 tokens on a repeat
    paste (hash cache); matching itself free (local embeddings + Python rerank).
*   **G5** — Corpus growth by one confirmation per paste (provisional records, curated-first
    matching) and manual outcome recording that feeds a typed outcome term in scoring.
*   **G6** — Zero new runtime dependencies beyond what the repo already ships
    (fastembed, ChromaDB, Groq client); free-tier only.

## Non-Goals

*   Per-claim web verification (deferred; later applies only to conclusion-changing claims
    the user cannot source themselves).
*   Automated news collectors or bulk ingestion.
*   Weight auto-tuning or any learned similarity on a small corpus.
*   Replacing the 10-agent debate: opinion/forecast questions stay on the debate; routing is
    explicit with a structural-guess default and one-click override.
*   Adding sentence-transformers/torch; hosting incident mode on Vercel (Docker/Koyeb only).
*   The debate pipeline reading incident records.
*   Non-English pastes (v1).

## Open Questions

*   **Excerpt commit**: `data/incidents/nvidia_2026/sources/nvidia_2026_sources.md` is
    designated but not yet in the tree; until it lands, the anchor case's `documented`
    claims load as `reported_unconfirmed` per the downgrade rule.
*   **Weak floor**: the 0.45 strong/weak threshold is a stated guess; calibrate once by
    leave-one-out self-matching after the 30-record corpus exists.
*   **Corpus list pre-commitment**: to guard against circular validation, the 30 titles
    should be fixed in writing before any scoring design is finalized.

## Critical User Journeys (CUJs)

### CUJ 1: Paste a live incident, get structural matches

*   **Given**: the server is running with the incidents collection built from ≥30 curated
    records; the user has a Groq key configured.
*   **When**: the user pastes a news report in incident mode and confirms the extracted
    fields in the review state.
*   **Then**: the panel shows the confirmed record, top-5 tiered matches with mechanical
    why/breaks bullets, `tag · source` on every claim, both timelines, and the closest
    match's recorded outcome; the response carries `retrieval_debug`; ~2.3k tokens or fewer
    consumed; an identical re-paste consumes 0 tokens.

### CUJ 2: Route a question to the right mode

*   **Given**: one input box with a mode selector (Debate | Incident) pre-set by the
    structural gate.
*   **When**: the user types a question-shaped input ("Will India's semiconductor policy
    succeed?") or pastes a multi-paragraph incident report.
*   **Then**: the gate pre-selects the matching mode; a wrong guess is corrected with one
    click and logged; dispatch happens before any coordinator construction, so a misrouted
    paste never triggers a Tavily search.

### CUJ 3: Record what happened next

*   **Given**: an incident exists in the corpus with no outcome yet.
*   **When**: the user pastes "what happened next" text for it.
*   **Then**: one small-model call maps it into typed outcome fields appended to the JSON
    record; no re-embed occurs; the panel immediately renders the outcome under that
    record's timeline; future matches involving this record gain the 0.05 outcome term.

### CUJ 4: Grow the corpus from normal use

*   **Given**: incident pastes are saved as provisional records behind the confirm step.
*   **When**: the curator reviews the provisional queue and promotes or prunes entries.
*   **Then**: promoted records join curated-first matching; pruned records leave the
    corpus; paste-hash dedupe prevents the same story from entering twice.

--------------------------------------------------------------------------------

## Technical Plan (Architecture)

### Component layout

A new top-level `incidents/` package sits beside `core/` and `rag/` (the reviewer-mandated
boundary: `core/` is already a 12-module accretion zone). Its shared surface with the debate
pipeline is exactly two imports — `vg.config` and `vg.core.llm_client` — and nothing else.

```text
incidents/
  schema.py      dataclass + strict enums + JSON round-trip/validation (stdlib only)
  constants.py   closed vocabularies: actor_roles, enum values, WEIGHTS dict (v1)
  scoring.py     pure functions; cosine is an injected parameter; no I/O, no LLM
  embedder.py    fastembed wrapper; single shared TextEmbedding instance (bge-small-en-v1.5)
  store.py       JSON files + Chroma collection; sole mutation point; threading.Lock;
                 atomic writes (temp file + os.replace); rebuild_index(); record_hash
  ingest.py      the one extraction call (async client, JSON mode, one repair retry,
                 tolerant parse); paste cap 4,000 chars; injectable extractor for tests
  match.py       orchestration: embed → retrieve top-20 → rerank → tier → mechanical
                 explanations → response assembly (incl. retrieval_debug)
  router.py      zero-token structural gate (question-shape → debate; length/date/entity
                 density → incident); logs overrides
  explain.py     mechanical why-matches / where-it-breaks from typed-field diffs;
                 optional small-model narrative gloss behind a flag
```

### Data stores and their contract

*   **Source of truth**: `data/incidents/<incident_id>.json` — human-authored for the 30
    curated records (outcomes pre-filled; extractor not involved, 0 tokens), auto-written
    for provisional records behind the confirm step.
*   **Derived cache**: Chroma collection `incidents` in the existing `./chroma_db` path,
    created with `hnsw:space='cosine'`; similarity is computed as `1 − distance` directly
    (the repo's `hybrid_retriever.py` converts cosine distances as if L2 — a bug this
    design does not inherit). `store.py` owns `rebuild_index()`: read all JSON files,
    upsert by `incident_id`; stores `record_hash` (sha256 of file bytes) in metadata; on
    server start (and optionally per query against top-20 candidates) a count/hash mismatch
    triggers a full rebuild, which is sub-second at 50 records. Chroma has zero authority:
    any hand edit of a JSON file is picked up on next start or query.
*   **Repeat cache**: keyed on `(sha256(paste), corpus_version)`; a byte-identical re-paste
    returns the cached ingest + match result without any model call.
*   **Raw paste spool**: failed extractions land in `data/incidents/_raw/` — no partial
    record ever reaches JSON or Chroma.

### Data flow

```text
                    ┌──────────────────────────────────────────────────────┐
 paste (≤4k chars)  │  web panel: mode selector (Debate | Incident)        │
 ──────────────────►│  pre-set by router.py structural gate                │
                    └───────────────┬─────────────────────────┬────────────┘
                          incident  │                         │  debate-shaped
                                    ▼                         ▼
                    ┌───────────────────────────┐   existing analyze_async()
                    │ POST /api/incident-match  │   → DebateCoordinator (untouched)
                    │  (table-dispatched route) │
                    └───────────┬───────────────┘
                                │ repeat? sha256(paste)+corpus_version cached →
                                │   return cached result, 0 model calls
                                ▼
                    ┌───────────────────────────┐
                    │ ingest.py: 1 small call   │  allam-2-7b, async, JSON mode,
                    │ extract schema + tags     │  45–60s timeout, 1 repair retry
                    └───────────┬───────────────┘
                                │  confirm/edit state (human checks fields)
                                ▼
              ┌─────────────────────────────────┐
              │ store.py: write JSON (atomic),  │
              │ upsert embedding into Chroma    │  (threading.Lock around mutation)
              └────────────────┬────────────────┘
                               ▼
     ┌───────────────────────────────────────────────────────────────┐
     │ match.py: embedder.py → top-20 by cosine (1 − distance)       │
     │ scoring.py rerank (typed fields, WEIGHTS v1) → strong/weak    │
     │ tiers → explain.py mechanical bullets from field diffs        │
     └───────────────┬───────────────────────────────────────────────┘
                     ▼
     response: matches + per-component scores + retrieval_debug
     (extracted-record echo, pre-rerank top-20 raw cosines)

  outcome path:  record_outcome(id, text) → 1 small call → typed outcome
                 fields appended to JSON; NO re-embed; reindex hash updates
```

### API changes

*   `api/server.py` — `do_POST` converts from a hardcoded `/api/analyze` comparison to a
    dispatch table; new route `POST /api/incident-match` reuses the existing `X-API-Key`
    handling (extraction and optional gloss are Groq calls). Typed failure responses:
    embedder unavailable → 503 with reason (never an empty result set); extraction
    invalid → `needs_manual_entry` + paste spooled; mechanical explanations are local, so
    a gloss failure never blocks the response. `GET` serving is untouched.
*   `api/index.py` (Vercel) — incident mode is out of scope there (read-only filesystem vs
    `PersistentClient` + model cache); the serverless path returns a clean 501 for
    `/api/incident-match` rather than a silent 404.
*   `main.py` — `run_web` startup adds the incidents analogue of the RAG auto-build:
    ensure the collection exists / rebuild from JSON before serving. Mode dispatch happens
    before any coordinator construction (the debate pipeline's first act is a Tavily call;
    a misrouted paste must not burn search quota).

### Integration points (existing code, unchanged behavior)

*   `config.py` — new keys following the existing env-var pattern, resolved to absolute
    paths anchored at the package root: `incidents_data_path`, `incidents_collection`,
    `incident_weak_threshold` (default 0.45 until calibrated).
*   `rag/builder.py` — `build_all()` gains `build_incidents()` (read JSON corpus, embed
    `summary_embed`, upsert into `incidents` with cosine space) so the Docker image
    pre-bakes the collection the same way it pre-bakes the wisdom collections.
*   `Dockerfile` — builder stage sets `FASTEMBED_CACHE_PATH` and copies the model cache
    (~130 MB) into the runtime image; a runtime cold start must not re-download the
    embedding model, because the matcher's primary signal is that embedding.
*   `core/llm_client.py` — used as-is via the existing async client; the shared RPM limiter
    is unaffected at incident volumes (2 calls per fresh paste). A known pre-existing bug
    (per-request `asyncio.run()` rebuilding the limiter in the threaded server) is noted;
    incident mode must not rely on cross-request limiting.
*   Web UI (`api/static/`) — incident results render in a full-height overlay (the current
    350px verdict aside cannot host the output contract), with a multiline paste box, the
    mode selector, an extracted-fields review/edit state before save, `tag · source`
    rendering on every claim, and both timelines.

### Scoring and explanation mechanics

*   `scoring.py` is deterministic given `(cosine, record, candidate)`: weights sum to 1.0
    (`0.25 cosine, 0.20 trigger_type, 0.15 roles-Jaccard, 0.10 constraint-Jaccard,
    0.10 escalation-Jaccard, 0.05 resolution, 0.05 tempo, 0.05 exit_authority,
    0.05 outcome-Jaccard`); `WEIGHTS_VERSION` is echoed in responses; a weight change
    forces a same-commit fixture update.
*   `explain.py` derives why-matches (shared/equal typed fields, weighted by their scoring
    contribution) and where-it-breaks (mismatched or missing fields) directly from the
    scorer's per-component output — the LLM never generates the default explanation. The
    optional gloss call receives the diff so it can annotate, not invent.
*   Empty-corpus and no-match behavior: `Jaccard(∅, ·) = 0`; if fewer than 3 of the top 5
    clear the weak floor, the panel states "no close structural match in history yet" and
    shows raw scores only — no confident why-it-matches text for matches that all break.

--------------------------------------------------------------------------------

## Alternatives Considered

### Alternative A: Embedding-only matching (no typed fields)

*   **Pros**: Simplest possible matcher — embed, retrieve, done; zero extraction
    requirements; no schema to maintain.
*   **Cons**: Embeddings track surface topics, not structure; two incidents with the same
    causal shape but different wording embed far apart, while unrelated incidents sharing
    vocabulary embed close together.
*   **Reason for Rejection**: Rejected in brainstorm: "same pattern, not same words" is the
    stated requirement, and topic similarity cannot deliver it. Typed fields
    (trigger_type, constraint_types, escalation, tempo, exit_authority) are the mechanism
    that makes structure matchable.

### Alternative B: LLM rerank of retrieved candidates

*   **Pros**: A stronger model can weigh subtle structural similarities that fixed field
    comparisons miss.
*   **Cons**: ~2–3k extra tokens per query on the free tier; non-deterministic; harder to
    audit than arithmetic; at N=30–50 the candidate set is small enough that typed-field
    scoring covers the discrimination needed.
*   **Reason for Rejection**: Rejected: token cost for marginal gain at corpus scale; the
    reranker's per-component scores are also what the mechanical explanations and
    `retrieval_debug` are built from, and a model-in-the-loop would break that audit chain.

### Alternative C: Auto-reweighting similarity from recorded outcomes

*   **Pros**: The "gets sharper" promise becomes automatic; no hand-set weights.
*   **Cons**: Overfits a small corpus; a few early outcomes would dominate the weights;
    unexplainable rank shifts.
*   **Reason for Rejection**: Rejected by author: no self-reweighting on a small corpus.
    Outcomes sharpen ranking through the fixed 0.05 typed outcome term instead.

### Alternative D: Component reframe — feed the corpus into the existing pattern-grounding path

*   **Pros**: Fewest new parts: `core/upset_patterns.py` already injects historical
    parallels into debate context; no second endpoint, panel, or mode.
*   **Cons**: The stated output contract (tiered top-5, provenance tags, dual timelines,
    closest-match outcome) has no home in the debate pipeline's rendering; incident
    queries would either run the full 10-agent debate (defeating the token goal) or need a
    rendering path anyway.
*   **Reason for Rejection**: Rejected by author (post-review decision): keep the dedicated
    second mode. The reframe remains a recorded fallback if the second mode proves
    redundant with the pattern-grounding path in practice.

### Alternative E: Replace the debate pipeline for all questions

*   **Pros**: One code path; no router.
*   **Cons**: Opinion and forecast questions genuinely need multi-persona deliberation;
    incident lookups cannot produce a verdict, and debate questions gain nothing from
    records.
*   **Reason for Rejection**: Rejected by author: beside, not replace — one router, two
    modes, with routing decided before any coordinator construction.

### Alternative F: Chroma metadata as the only store

*   **Pros**: No second store to keep in sync.
*   **Cons**: Chroma metadata is scalar-only; claims, timelines, and outcomes cannot be
    stored losslessly, and human editing of records becomes impractical.
*   **Reason for Rejection**: Rejected: JSON files as the human-editable source of truth
    with Chroma as a rebuildable derived index — the reverse of this alternative.

### Alternative G: sentence-transformers / MiniLM embeddings

*   **Pros**: The most widely documented local embedding stack.
*   **Cons**: Drags in torch (~2 GB installed); the repo standardizes on fastembed (ONNX)
    with `BAAI/bge-small-en-v1.5`, already pre-baked in Docker; MiniLM and bge-small are
    different vector spaces, so scores are not interchangeable with anything already in
    Chroma; torch risks OOM on 512 MB free-tier containers.
*   **Reason for Rejection**: Rejected after codebase review: reuse the existing
    fastembed/bge-small stack; zero new runtime dependencies is an explicit goal.

### Alternative H: LLM-classifier routing (or toggle-only routing)

*   **Pros**: A classifier routes frictionlessly; a pure toggle costs nothing and is
    unambiguous.
*   **Cons**: The classifier costs tokens per question and misroutes (a misroute sends a
    paste to Tavily and the debate cache); toggle-only adds friction to every query.
*   **Reason for Rejection**: Rejected in favor of a zero-token structural gate (input
    shape, date patterns, entity density) that pre-sets a visible mode selector, with a
    one-click override and override logging — the ambiguity band is handled by the human,
    not by a paid guess.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Security & Privacy**: pasted text is user content and is stored (provisional records,
    `_raw/` spool) locally only — the corpus is not published. `POST /api/incident-match`
    and `POST /api/incident-outcome` reuse the existing `X-API-Key` handling; no new
    secrets; Groq key usage unchanged.
*   **Performance & Latency**: per fresh paste — one Groq call (45–60s explicit timeout) plus
    local embed/rerank (< ~1s at N≤50); index rebuild sub-second; one shared fastembed ONNX
    model (~130 MB cache, no torch) sized for 512 MB free-tier containers.
*   **Token overhead**: ≤ ~2.3k API tokens per fresh incident, 0 on repeat (hash cache);
    usage read from Groq responses and logged per call for the audit trail.
*   **Rollout & Rollback**: the feature is additive — new package plus new dispatch-table
    entries. Rollback = remove the two route entries and the `incidents/` imports; the JSON
    corpus is untouched. No migrations in v1; an enum rename would require a one-line
    migration plus reindex and is called out as such.

## Additional Resources

*   `concepts_brief.md` (v2, post-7-lens-Goldfish review) — authoritative source for schema,
    weights, tag rules, token math.
*   Repo modules cited in the Technical Plan: `core/debate.py`, `core/llm_client.py`,
    `rag/builder.py`, `rag/hybrid_retriever.py`, `api/server.py`, `config.py`, `Dockerfile`.

## Future Improvements

*   **Web verification**: verify only conclusion-changing claims the user cannot source
    themselves (post-v1).
*   **Corpus scaling trigger**: if the corpus passes ~100 records or ingest frequency makes
    hand-filing the bottleneck, revisit bulk collectors and weight recalibration.
*   **Component reframe fallback**: if the second mode proves redundant with the
    pattern-grounding path in practice, feed the corpus into `upset_patterns` and retire the
    dedicated endpoint.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

### Build sequence

Steps 0–4 in order. **Step 0 is a hard precondition gate**: no `incidents/` code is written
until the tree is single-copy. File numbering is global; each file notes its step.

### Target Files to Create/Modify

#### Step 0 — Reconcile the tree (precondition)

#### 1. `cli.py` (Delete)

*   **Type / Scope**: CLI entry point.
*   **Proposed Changes**: Delete. The web-only build landed on the divergent copy; nothing
    imports this file (verified). Its removal is what Step 0 exists to finish.

#### 2. `vg-main/` (Delete)

*   **Type / Scope**: Untracked divergent app copy (incl. `__pycache__`).
*   **Proposed Changes**: Diff its web-only `main.py` against root first (it is the
    reference shape for file 5), then delete the directory.

#### 3. `testapp/` (Delete)

*   **Type / Scope**: Third full app copy (`api/`, `core/`, `agents/`, `search/`,
    `config.py`, `main.py`).
*   **Proposed Changes**: Delete; confirmed untracked and unreferenced by the readiness
    review.

#### 4. Root `test_agents.py`, `test_api.py`, `test_cache.py`, `test_run.py`, `test_runner.py`, `test_simulation.py` (Delete/Merge)

*   **Type / Scope**: Orphaned root test files (also collected by pytest, alongside `tests/`).
*   **Proposed Changes**: Audit each against `tests/`: delete where coverage duplicates
    `tests/` or exercises deleted CLI paths; move any unique coverage into `tests/` before
    deleting.

#### 5. `main.py` (Modify)

*   **Type / Scope**: Entry point (`analyze_async`, `analyze`, `run_web`).
*   **Proposed Changes**: Strip to the pinned keep-list — `analyze_async`, `analyze`,
    `run_web`, `_consume_option` stay; `run_cli`, `print_report`, `byok_setup`, and the
    `--cli/--json/--basic` argv handling go. Behavior byte-equivalent to the web-only
    `vg-main/main.py` shape plus the `_consume_option` diff. All importers (`api/server.py`,
    `api/index.py`, `run.py`, Dockerfile CMD, Procfile) keep working unchanged.

#### 6. `README.md` (Modify)

*   **Type / Scope**: Docs.
*   **Proposed Changes**: Usage section drops CLI invocations; documents web UI and
    programmatic `analyze()` use.

#### 7. `QUICKSTART.md` (Modify)

*   **Type / Scope**: Docs.
*   **Proposed Changes**: Fix the broken `cd vg` invocation → run `python run.py` from the
    repo root.

#### 8. `rag/builder.py` (Modify)

*   **Type / Scope**: Docstring fix only (substantive edit comes in Step 1).
*   **Proposed Changes**: Correct stale `python -m veritas.rag.builder` to
    `python -m vg.rag.builder`.

#### 9. `.env.example` (Modify)

*   **Type / Scope**: Config template.
*   **Proposed Changes**: Fix the stale "MUDDL API Keys" header.

#### Step 1 — Schema freeze + corpus + store

#### 10. `incidents/__init__.py` (Create)

*   **Type / Scope**: Python package marker.
*   **Proposed Changes**: Re-export the public surface: schema types, store functions,
    match orchestration entry. Nothing from `core/` beyond `config` and `llm_client` may be
    imported anywhere in this package.

#### 11. `incidents/constants.py` (Create)

*   **Type / Scope**: Constants module.
*   **Proposed Changes**: Closed vocabularies (`actor_roles`, every enum's values) and the
    hand-set `WEIGHTS` dict (0.25 cosine / 0.20 trigger / 0.15 roles / 0.10 constraint /
    0.10 escalation / 0.05 resolution / 0.05 tempo / 0.05 exit_authority / 0.05 outcome)
    with `WEIGHTS_VERSION = 1`. Module-level constants only; no logic.

#### 12. `incidents/schema.py` (Create)

*   **Type / Scope**: Python dataclass + validation (stdlib only).
*   **Proposed Changes**: Incident record dataclass, strict enums, JSON round-trip and
    validation (bad enum/field → `ValueError` listing fields). Load-time provenance rule: a
    `documented` claim whose excerpt file is absent under
    `data/incidents/<id>/sources/` loads as `reported_unconfirmed`. Fixed
    `summary_embed` template function over canonical fields only (model never writes it;
    template change ⇒ full re-embed). Claim ids assigned `c1…cn` in list order, local to
    the record.

#### 13. `incidents/store.py` (Create)

*   **Type / Scope**: Persistence layer (JSON + ChromaDB).
*   **Proposed Changes**: Sole mutation point. `threading.Lock` around every JSON+Chroma
    mutation; atomic writes (temp file + `os.replace`); `rebuild_index()` (read all JSON,
    upsert by `incident_id`; sub-second at N≤50); `record_hash` (sha256 of file bytes)
    stored in Chroma metadata; count/hash drift check at server start and per query against
    top-20 candidates. Collection created with `hnsw:space='cosine'`; single encode/decode
    pair for `;`-joined list metadata. Paste-hash repeat cache read/write.

#### 14. `incidents/embedder.py` (Create)

*   **Type / Scope**: Embedding wrapper.
*   **Proposed Changes**: Single shared lazily-created fastembed `TextEmbedding`
    (`BAAI/bge-small-en-v1.5`). Unavailability raises a typed error → 503 upstream — never
    an empty result set (does not inherit the repo's silent-`[]` retriever pattern).

#### 15. `data/incidents/README.md` (Create)

*   **Type / Scope**: Corpus authoring guide.
*   **Proposed Changes**: One template record plus the authoring rules: records are
    hand-authored JSON (extractor not involved), outcomes pre-filled for settled cases,
    `documented` claims carry excerpt refs, and the 30-title corpus list is committed
    before scoring design is finalized.

#### 16. `data/incidents/*.json` × 30 (Create — user-authored)

*   **Type / Scope**: Curated corpus records.
*   **Proposed Changes**: Authored by the curator, not by this implementation; outcomes
    pre-filled; claims tagged with real source refs. The Nvidia record is **excluded** —
    it enters as held-out demo #31 after the 30 exist.

#### 17. `config.py` (Modify)

*   **Type / Scope**: Configuration.
*   **Proposed Changes**: New keys following the existing env-var pattern, resolved to
    absolute paths anchored at the package root (never CWD-relative):
    `incidents_data_path`, `incidents_collection`, `incident_weak_threshold`
    (default 0.45 until calibrated).

#### 18. `rag/builder.py` (Modify)

*   **Type / Scope**: Index builder.
*   **Proposed Changes**: `build_incidents()` added to `build_all()` — read the JSON corpus,
    embed `summary_embed`, upsert into the `incidents` cosine collection, so the Docker
    image pre-bakes the collection the way it pre-bakes the wisdom collections.

#### 19. `Dockerfile` (Modify)

*   **Type / Scope**: Build configuration.
*   **Proposed Changes**: Builder stage sets `FASTEMBED_CACHE_PATH` and copies the model
    cache (~130 MB) into the runtime image; a cold start must not re-download the embedding
    model, because the matcher's primary signal is that embedding.

#### 20. `tests/test_incident_schema.py` (Create)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: JSON round-trip; enum validation errors; the downgrade rule in
    both directions (excerpt present → `documented`, absent → `reported_unconfirmed`);
    `summary_embed` template determinism. Offline; follows the existing `tests/` sys.path
    shim convention.

#### Step 2 — Scoring + match + endpoint

#### 21. `incidents/scoring.py` (Create)

*   **Type / Scope**: Pure scoring functions (no I/O, no LLM, no Chroma imports).
*   **Proposed Changes**: Score given `(cosine, record, candidate)` with cosine injected as
    a parameter; returns the score plus per-component contributions; `Jaccard(∅, ·) = 0`;
    tiering (strong/weak against `incident_weak_threshold`);
    `calibrate_weak_floor()` via leave-one-out self-matching (run once post-corpus).

#### 22. `incidents/match.py` (Create)

*   **Type / Scope**: Match orchestration.
*   **Proposed Changes**: Ensure index → embed → top-20 by `1 − distance` → rerank → tier →
    assemble response including `retrieval_debug` (extracted-record echo, pre-rerank top-20
    with raw cosines, per-component contributions). Empty corpus → `{"matches": [],
    "corpus_size": 0}`; fewer than 3 of the top 5 above the floor → raw-scores-only payload
    with the "no close structural match" state.

#### 23. `api/server.py` (Modify)

*   **Type / Scope**: Web server.
*   **Proposed Changes**: `do_POST` hardcoded comparison → dispatch table
    (`{"/api/analyze": …, "/api/incident-match": …}`). New route reuses the existing
    `X-API-Key` handling. Typed failures: embedder down → 503 with reason; invalid
    extraction → `needs_manual_entry` with the paste spooled. GET serving untouched.

#### 24. `main.py` (Modify)

*   **Type / Scope**: Entry point, startup path.
*   **Proposed Changes**: `run_web` startup gains the incidents analogue of the RAG
    auto-build: ensure the `incidents` collection exists / rebuild from JSON before
    serving (the RAG check only fires when `chroma.sqlite3` is absent, which never happens
    in the baked image).

#### 25. `tests/test_incident_scoring.py` (Create)

*   **Type / Scope**: Golden fixture tests.
*   **Proposed Changes**: Nvidia record + five analogs as JSON fixtures; cosine stubbed;
    per-component contributions asserted within ±0.01; one test asserts weights sum to 1.0;
    **pass criterion = correct top-5 ordering, never absolute scores**.

#### 26. `tests/test_incident_match.py` (Create)

*   **Type / Scope**: Integration tests (no network).
*   **Proposed Changes**: Fake deterministic embedder; `VG_CHROMA_PATH` → tmp dir; empty
    corpus behavior; `retrieval_debug` shape; hash-mismatch triggers rebuild; no fixture
    touches Groq.

#### Step 3 — Ingest + explain + router + panel

#### 27. `incidents/ingest.py` (Create)

*   **Type / Scope**: Extraction (the one small-model call).
*   **Proposed Changes**: Async client (`allam-2-7b`), JSON mode
    (`response_format={"type":"json_object"}`), explicit 45–60s timeout, one repair retry,
    tolerant-parse fallback. Paste cap 4,000 chars; English-only; multi-incident paste →
    extract the dominant incident or reject. Injectable extractor so tests never hit Groq.
    Failure → `needs_manual_entry`, raw paste spooled to `data/incidents/_raw/`, no partial
    record written. Also `extract_outcome()` (same call pattern) for the outcome loop.

#### 28. `incidents/explain.py` (Create)

*   **Type / Scope**: Explanation generator.
*   **Proposed Changes**: Mechanical why-matches / where-it-breaks bullets derived from the
    scorer's per-component output (weighted by contribution) — zero tokens. Optional
    small-model narrative gloss behind a flag receives the diff and can only annotate,
    never invent.

#### 29. `incidents/router.py` (Create)

*   **Type / Scope**: Mode router.
*   **Proposed Changes**: Zero-token structural gate (question shape → debate; length +
    date patterns + entity density → incident); logs overrides. Runs before any
    coordinator construction, so a misroute never triggers the debate pipeline's Tavily
    call.

#### 30. `api/server.py` (Modify)

*   **Type / Scope**: Web server.
*   **Proposed Changes**: Add `POST /api/incident-outcome` to the dispatch table: one small
    call maps pasted follow-up text into typed outcome fields; nothing partial is written
    on failure.

#### 31. `api/index.py` (Modify)

*   **Type / Scope**: Vercel serverless handler.
*   **Proposed Changes**: Both incident routes return a clean 501 — Vercel is out of scope
    for incident mode (read-only filesystem vs `PersistentClient` + model cache).

#### 32. `api/static/index.html` (Modify)

*   **Type / Scope**: Web UI.
*   **Proposed Changes**: Mode selector (Debate | Incident) above the input; multiline
    paste box for incident mode; full-height overlay panel (the current 350px aside cannot
    host the output contract); extracted-fields review/edit state between extract and
    save. Styles live where the file already carries them.

#### 33. `api/static/app.js` (Modify)

*   **Type / Scope**: Web UI logic.
*   **Proposed Changes**: Panel flow — extract → review → confirm → render (strong/weak
    tiers, `tag · source` on every claim, both timelines, closest-match outcome, the
    "no close structural match in history yet" state); one-click mode override with
    logging; repeat-paste cache indicator.

#### 34. `tests/test_incident_ingest.py` (Create)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: Stub extractor — paste-cap enforcement, repair-retry path,
    `needs_manual_entry` + spool behavior, outcome extraction mapping. Never hits Groq.

#### 35. `tests/test_incident_router.py` (Create)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: Classification table for the structural gate; override logging.

#### Step 4 — Outcomes + growth

#### 36. `incidents/store.py` (Modify)

*   **Type / Scope**: Persistence layer.
*   **Proposed Changes**: `record_outcome()` — typed outcome fields via
    `ingest.extract_outcome`, JSON-only update (**no re-embed**: `summary_embed` excludes
    outcome fields), `record_hash` refresh. Promote/prune = direct JSON status edit
    (documented; no endpoint — see cuts). Under the same lock as every other mutation.

#### 37. `tests/test_incident_outcome.py` (Create)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: Outcome write path — no re-embed, hash refresh, the outcome
    renders in subsequent match payloads; a failed extraction writes nothing.

### Explicit cuts (considered, not built)

*   No `/api/incident-promote` endpoint — promote/prune is a direct JSON edit; the index
    rebuilds on hash drift.
*   No separate calibration CLI — `calibrate_weak_floor()` is a tested function run once
    after the corpus exists.
*   No standalone gloss endpoint — the gloss flag rides inside `/api/incident-match`.
*   No incident implementation in `api/index.py` — 501 only.

### Verification Plan

*   **Compilation/Build**: `python -m compileall incidents/` plus an import smoke
    (`python -c "import vg.main, vg.api.server"`). No linter is configured in the repo;
    nothing new is introduced.
*   **Unit Tests**: `pytest tests/` — all new suites run offline (stub extractor, fake
    embedder, `VG_CHROMA_PATH` → tmp dir); the golden scoring suite (file 25) is the
    correctness gate with the ordering-only criterion; file 20 covers the downgrade rule in
    both directions.
*   **Test Coverage Requirement**: every `incidents/` module carries its own suite; the
    scorer's per-component arithmetic is asserted to ±0.01, not just final scores.
*   **E2E/Manual**: curl smoke of extract → review → confirm against a running server;
    typed failures exercised (oversized paste, unparseable paste, embedder path missing →
    503); Docker build verified to contain the `incidents` collection and the model cache,
    with a cold start that does not re-download; token audit from Groq response usage
    (≤ ~2.3k fresh, 0 on a repeat paste); the Nvidia held-out demo runs only after the
    30-record corpus exists, with observed ordering recorded; committing the excerpt file
    flips the anchor case's claims to `documented` (downgrade rule verified live).

--------------------------------------------------------------------------------

*Drafted with EGM*
