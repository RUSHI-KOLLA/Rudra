# Incident Memory: Structural Match Against Recorded History

*   **Author:** Rushi
*   **Status:** Approved
*   **Date:** 2026-11-17
*   **Revised:** 2026-11-17 — zero-agent incident mode; gap-driven research loop; debate
    parked behind a default-off flag; six-file package; base rate, silence line, as-of dating.

--------------------------------------------------------------------------------

## Overview

VG answers questions in two modes. Incident mode — the default and primary mode — has no
agents at all. The user pastes a live news incident; the system extracts a structured card
(one model call, every claim tagged by provenance), embeds it, and scores it against a
curated corpus of recorded history — same pattern, not same words — returning the top-5
matches in strong/weak/no-match tiers with mechanically generated why-it-matches and
where-it-breaks bullets, a base rate, and a silence line, all stamped "as of <date>". It
then raises up to 5 research questions per round (≤10 total), each derived mechanically
from one of four gap types,
runs one search per question, writes back tagged answers through existing card fields, and
re-scores. The 10-agent debate pipeline is kept but parked behind a single flag, default
off, reserved for forecast questions only; incident mode constructs no agents. The corpus
grows as a side effect of use: every pasted incident can be saved as a provisional record
with one confirmation, and recorded outcomes sharpen ranking. Everything runs on the repo's
existing free-tier stack: one small-model extraction call, local fastembed embeddings,
ChromaDB, plain Python, and the Tavily search the repo already ships.

## The Problem

When a live incident breaks, the useful question is not "what would ten personas say" but
"when has this shape happened before, and what happened next?" Three concrete gaps:

1.  **No incident memory.** The repo has no store of real incidents. `core/upset_patterns.py`
    holds ~a dozen hand-written case entries keyed to coarse pattern labels — a single year
    and a prose outcome each, no actor structure, no excerpt-anchored claims, matched by
    keyword overlap only; the RAG layer holds wisdom prose. Neither can answer "give me
    the five closest recorded analogs and what followed each."
2.  **No provenance.** LLM output cannot distinguish what a primary document establishes
    from what a reporter attributes from what a model inferred — and for the anchor case
    (NVIDIA, 2026-11-12), the primary 8-K is silent on the resignation's cause, which is
    exactly the fact any narrative would be tempted to paper over.
3.  **Cost without memory.** The debate pipeline spends ~16.5k–66.8k tokens per question.
    A lookup against recorded structure should cost an order of magnitude less.

The solution: a typed incident schema; structural matching by local embeddings plus
typed-field scoring; explanations generated mechanically from field diffs; provenance tags
anchored to stored document excerpts; a grounded, gap-driven research loop (questions only
from mechanical gap detectors, one search each, maximum two rounds, a mechanical stop
rule); a one-confirmation growth path for the corpus; and an outcome-recording loop.

### Provenance status of the anchor case

The Nvidia case is **documented**. The author holds two primary artifacts, with excerpts
designated for `data/incidents/nvidia_2026/sources/nvidia_2026_sources.md`:

*   SEC Form 8-K, Item 5.02 — event date 2026-11-11, filed 2026-11-12, accession
    `0001045810-26-000082`
*   NVIDIA investor press release, dated 2026-11-12

Tag split, stated explicitly:

*   `documented` — resignation as President, CEO, and board member effective immediately;
    Colette Kress appointed interim CEO; Harvey C. Jones appointed Chair; a 33-year tenure
    (press release wording).
*   `reported_unconfirmed` — the affairs; the intelligence assessment that a relationship
    partner was a foreign asset; the 13% share drop.
*   The 8-K gives **no reason** for the resignation. Every rendering of this record must say
    so plainly: the primary document is silent on cause, and that silence is the hinge the
    whole explanatory chain turns on. The matcher must not fill it with press narrative.

A classified intelligence assessment can never reach `documented` — that note is UI copy,
not an ingest rule. The excerpt file is the artifact anchor: until it is committed to the
tree, the load-time rule (see the schema section) keeps the affected claims at
`reported_unconfirmed`.

## Goals

*   **G1** — For any pasted incident (English, ≤4,000 characters), return the top-5
    historical matches in strong/weak/no-match tiers, each with why-it-matches and
    where-it-breaks bullets generated mechanically from typed-field comparisons, plus a
    base rate, a silence line, and an "as of <date>" stamp.
*   **G2** — Every claim rendered anywhere carries exactly one provenance tag
    (`documented` | `reported_unconfirmed` | `inferred` | `speculative`) with its source;
    `documented` requires the document excerpt in the record, with a load-time downgrade
    to `reported_unconfirmed` if the excerpt file is absent.
*   **G3** — Render two timelines per query: the pasted incident's (extracted at ingest) and
    each match's (stored), with the closest match's recorded outcome appended beneath its
    timeline.
*   **G4** — Hard ceiling of 3.5k LLM tokens per fresh incident (the one extraction call,
    plus at most one repair retry). On retry, the same prompt is re-sent with the parse
    error appended; there is no second retry. The gap loop adds zero LLM tokens
    (templated questions, mechanically tagged answers; up to ten Tavily searches are API
    quota, not model tokens); 0 tokens and 0 searches on a repeat paste (hash cache);
    matching itself free (local embeddings + Python rerank).
*   **G5** — Corpus growth by one confirmation per paste. v1 matches against curated
    records only; provisional cards are never match candidates — they surface only as
    "you have seen something like this before." Manual outcome recording feeds a typed
    outcome term in scoring.
*   **G6** — Zero new runtime dependencies beyond what the repo already ships
    (fastembed, ChromaDB, Groq client, Tavily); free-tier only.
*   **G7** — The research loop is grounded, never free-running: questions may come only
    from the four mechanical gap detectors (empty card field, expected evidence missing,
    claim contradiction, no matching card in memory); each question gets exactly one
    search; the answer is written back with a source and a provenance tag or marked "no
    source available"; maximum two rounds; the loop stops only when nothing further can be
    closed with available sources, every remaining open gap has returned "no source
    available", or the two-round cap is reached — never on a model's judgement.
*   **G8** — The 10-agent debate pipeline is out of the incident path entirely: kept,
    parked behind one flag (default off), reserved for forecast questions only. No reduced
    agent panel exists in incident mode.

## Non-Goals

*   Per-claim web verification (deferred; later applies only to conclusion-changing claims
    the user cannot source themselves).
*   Automated news collectors or bulk ingestion.
*   Weight auto-tuning or any learned similarity on a small corpus.
*   Replacing or shrinking the 10-agent debate inside incident mode: it is parked behind a
    flag (default off) for forecast questions only; no reduced agent panel is kept in
    incident mode "just in case".
*   Free-running research loops: no model-decided question generation, no model-decided
    stopping, no per-claim web verification beyond the one-search-per-gap loop.
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
    are committed as `data/incidents/_corpus_list.md` before any scoring code exists.
    Nvidia stays out of the corpus until after weak-floor calibration; calibration is
    leave-one-out only.
*   **Search quota**: the gap loop spends up to ten Tavily searches per fresh paste; the
    free tier's quota headroom against real usage is unknown until exercised.

## Critical User Journeys (CUJs)

### CUJ 1: Paste a live incident, get structural matches

*   **Given**: the server is running with the incidents collection built from ≥30 curated
    records; the user has a Groq key configured.
*   **When**: the user pastes a news report in incident mode and confirms the extracted
    fields in the review state.
*   **Then**: the panel shows the confirmed card, top-5 matches in strong/weak/no-match
    tiers with mechanical why/breaks bullets, the base rate, the silence line, `tag ·
    source` on every claim, both timelines, and the closest match's recorded outcome — all
    stamped "as of <date>"; up to 5 research questions per round (≤10 total) were raised
    only from mechanical gap detectors, each answered by exactly one search with a tagged
    write-back or an explicit "no source available", in at most two rounds, followed by a re-score; the response
    carries `retrieval_debug` {extracted_record, corpus_version, weights_version, weak_threshold, excluded_provisional_count, candidates:[{id, score, components:{each weighted term}, cosine}]} top 20 pre-tier and the loop audit; ≤ ~2.3k LLM tokens consumed; an identical
    re-paste consumes 0 tokens and 0 searches.

### CUJ 2: Route between incident mode and the parked debate

*   **Given**: one input box with a mode selector (Incident | Debate); the debate flag is
    off by default; the Debate option is hidden while the flag is off.
*   **When**: the user types a question-shaped input ("Will India's semiconductor policy
    succeed?") or pastes a multi-paragraph incident report.
*   **Then**: the explicit mode field selects incident or debate (default incident when
    absent); with the flag off and a forecast question, return 409 with "forecast mode
    disabled" — never silently fall back to incident matching; with the flag on, forecast
    questions run the parked debate pipeline unchanged; no heuristics, no guessing from
    question shape; dispatch happens before any coordinator construction.

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
    corpus; paste-hash dedupe catches byte-identical re-pastes; a re-worded duplicate is not caught.

--------------------------------------------------------------------------------

## Technical Plan (Architecture)

### Component layout

A small `incidents/` package sits at the repo root beside `core/` and `rag/` — six logic
files plus a package marker. On disk it lives at `vg/incidents/` (the repo root *is* the
`vg` package), so every module is imported as `vg.incidents.*`. Incident mode shares
exactly three imports with the rest of the repo — `vg.config`, `vg.core.llm_client`, and
`vg.search.web` (search only) — and nothing else; it never imports the agent
implementations or the debate coordinators.

```text
incidents/
  __init__.py    package marker; re-exports the public surface
  schema.py      card dataclass, strict enums, closed vocabularies, mechanical tag
                 cascade, summary_embed template, load-time provenance downgrade
  store.py       JSON cards + Chroma index (derived cache only): load/save, atomic
                 writes, threading.Lock, rebuildable index, shared fastembed
                 instance, paste-hash repeat cache
  scoring.py     pure typed-field score (cosine injected), per-component
                 contributions, mechanically generated why-matches /
                 where-it-breaks, tiers, base rate
  gaps.py        the four gap detectors + expected-evidence profile +
                 templated questions (zero model calls)
  research.py    one search per question, tagged write-back, "no source
                 available", max-two-rounds controller, mechanical stop rule
  match.py       orchestration: extract card → score → gaps → research →
                 re-score → response (retrieval_debug + loop audit + as_of);
                 the structural mode gate lives here as a small function
```

### Incident record schema

Source of truth: `data/incidents/<incident_id>.json` (human-authored for curated records).

```yaml
incident_id: str                  # deterministic: title + year; collision → ask user
title: str
status: enum                      # curated | provisional
date: date
recorded_at: date
actors: list[str]                 # people by common name, orgs by short name
actor_roles: list[str]            # CLOSED flat vocabulary of twelve: ceo, founder, cfo,
                                  # board, employee, regulator, court, intelligence_agency,
                                  # government, investor, customer, media. NOT positionally
                                  # aligned with actors. Adding a value is a schema version
                                  # bump.
sector: str
geography: str
trigger: str                      # free sentence — display only, never embedded
trigger_type: enum                # personal_conduct | market_shock | regulatory |
                                  # internal_conflict | external_attack | policy_shift
                                  # (several apply → first onset cause)
constraint_types: list[enum]      # legal | regulatory | market | reputational | security
                                  # (list; dominance precedence legal > regulatory >
                                  # market > reputational > security)
legal_outcome: enum               # none | pending | charges_dropped | convicted |
                                  # acquitted | settled
escalation_vector: list[enum]     # leak | filing | inquiry | ultimatum |
                                  # resign_signal | media_cycle
tempo: enum                       # hours | days | weeks | months
exit_authority: enum              # self | board | investors | court | regulator | electorate
succession: enum                  # internal | external | contested | unknown
timeline: list[{date, event, claim_ids}]
resolution: list[enum]            # primary first: resignation | dismissal | settlement |
                                  # ongoing | acquittal | conviction | bankruptcy |
                                  # dissolution | grounding
outcome: {summary, actors: list[str], constraint_types: list[enum],
          recorded_at, sources}   # pre-filled for curated records; empty for live pastes.
                                  # Outcomes are user-entered JSON edits through the panel;
                                  # no model ever writes an outcome. Promotion from
                                  # provisional to curated requires an outcome plus at least
                                  # one attached source; otherwise stays provisional.
claims: list[{id, text, tag, source_ids, supports: list[claim_id]}]
  tag: enum                       # documented | reported_unconfirmed | inferred | speculative
                                  # Cascade order (fixed): speculative → documented →
                                  # reported_unconfirmed → inferred. Forward-looking beats
                                  # everything. `documented` requires the excerpt file
                                  # present at load. `inferred` requires a non-empty
                                  # supports list; without it, downgrade to
                                  # reported_unconfirmed.
sources: list[{id, type, ref, date}]   # ref points to a stored excerpt for documented claims
summary_embed: str                # fixed Python template over canonical fields only:
                                   # trigger_type, sorted(actor_roles),
                                   # sorted(constraint_types), escalation_vector (in order),
                                   # resolution[0], tempo, exit_authority, succession,
                                   # sector. Free-text trigger and geography are excluded
                                   # — both reward surface similarity over structure.
                                   # Model never writes it; template change ⇒ full re-embed.
                                  # writes it; template change ⇒ full re-embed
```

Provenance rule: for `documented` claims, `sources[].ref` points to a stored excerpt file
under `data/incidents/<id>/sources/`; at load time, a documented claim whose excerpt file is
absent is downgraded to `reported_unconfirmed`.

Schema fields are unchanged from the approved v2 set; the gap loop adds none. Research
answers are written back through existing fields only — new `claims` entries with
`sources` refs (the search URL), fills of empty fields, and timeline entries — so a card
saved after the loop stays within the same schema. The loop's audit trail (questions asked,
gap types, search queries, closed/no-source status) rides in the API response, not in the
card.

### Claim tagging — precedence cascade

Applied mechanically at ingest, in order:

1.  Forward-looking or hypothetical → `speculative` (such claims never supply
    matching-field values).
2.  Primary source directly cited in the paste **and** the document is attached with its
    excerpt stored → `documented`.
3.  No primary document → `reported_unconfirmed` (covers attributed media reporting and
    bare assertions alike: provenance stops short of a primary document).
4.  Residual conclusions drawn from other claims → `inferred`, listing supporting claim ids
    in `supports`.

Tags describe the paste's provenance, never ground truth; rendered as `tag · source` on
every claim. The post-v1 web-verification plan shrinks to claims the user *cannot* source.

Research answers obey the same cascade with a hard ceiling: a search result carries no
primary document, so a mechanically tagged answer can be no better than
`reported_unconfirmed` with its source URL. It reaches `documented` only if the user later
attaches the underlying document to the card. Every question object must carry
`gap_type` and `gap_ref`; research.py refuses to dispatch a question lacking either.

### Data stores and their contract

*   **Source of truth**: `data/incidents/<incident_id>.json` — human-authored for the 30
    curated records (outcomes pre-filled; extractor not involved, 0 tokens), auto-written
    for provisional records behind the confirm step.
*   **Derived cache**: Chroma collection `incidents` in the existing `./chroma_db` path,
    created with `hnsw:space='cosine'`; similarity is computed as `1 − distance` directly
    (the repo's `hybrid_retriever.py` converts cosine distances as if L2 — a bug this
    design does not inherit). `store.py` owns `rebuild_index()`: read all JSON files,
    upsert by `incident_id`; stores `record_hash` (sha256 of file bytes),
    `WEIGHTS_VERSION`, and `TEMPLATE_VERSION` in metadata; on server start, any mismatch
    among these three version markers triggers a full rebuild, which is sub-second at
    50 records. No partial rebuilds, no migration code. Chroma has zero authority: any
    hand edit of a JSON file is picked up on next start.
*   **Repeat cache**: keyed on `(sha256(paste), corpus_version)`; a byte-identical re-paste
    returns the cached ingest + match result without any model call.
*   **Raw paste spool**: failed extractions land in `data/incidents/_raw/` — no partial
    record ever reaches JSON or Chroma.

### Data flow

```text
 paste (≤4k chars)
 ─────────────────► web panel: mode selector (Incident | Debate),
                     explicit mode field, default incident
                          │
            incident ─────┴───── forecast (flag on)
                │                      │
                ▼                      ▼
   POST /api/incident-match    POST /api/analyze
   (table-dispatched)          flag off → typed "debate disabled"
                │              response; flag on → debate pipeline
                │ repeat? sha256(paste)+corpus_version cached →
                │   return cached result: 0 model calls, 0 searches
                ▼
   match.py: extract card — the one small call
   (allam-2-7b, async, JSON mode, 45–60s timeout, 1 repair retry,
    claims tagged via the cascade; failure → needs_manual_entry if trigger_type or fewer
    than two actors can be filled, save the raw paste to data/incidents/_raw/, write no card)
                │  confirm/edit state governs SAVING only;
                ▼  matching runs on the in-memory card
   scoring.py: embed (store's shared instance) → top-20 by cosine
   (1 − distance) → typed-field rerank (WEIGHTS v1) → strong/weak/
   no-match tiers → mechanical why/breaks bullets → base rate
                │
                ▼
   gaps.py: four detectors → up to 5 templated questions per round (≤10 total)
   research.py: one search per question (Tavily, per-query dedupe)
   → tagged write-back via existing fields, or "no source available"
   → max 2 rounds → mechanical stop rule
                │  re-embed (filled fields change summary_embed; free)
                ▼  re-score
   response: tiers + per-component scores + base rate + silence line
   + "as of <date>" + retrieval_debug + loop audit

  outcome path:  record_outcome(id, text) → 1 small call → typed outcome
                 fields appended to JSON; NO re-embed; reindex hash updates
```

### API changes

*   `api/server.py` — `do_POST` converts from a hardcoded `/api/analyze` comparison to a
    dispatch table (`{"/api/analyze": …, "/api/incident-match": …,
    "/api/incident-outcome": …}`). The incident routes reuse the existing `X-API-Key`
    handling (extraction and outcome mapping are Groq calls). Typed failure responses:
    embedder unavailable → 503 with reason (never an empty result set); extraction
    invalid → `needs_manual_entry` + paste spooled; search unavailable → the affected
    questions return "no source available" and the response still completes. `GET`
    serving is untouched.
*   `/api/analyze` (debate) — gated by one config flag (`debate_enabled`, default **off**).
    With the flag off and a forecast question, return 409 with "forecast mode disabled"
    without constructing a coordinator; never silently fall back to incident matching.
    With the flag on it behaves exactly as today (`EnhancedDebateCoordinator`) and serves
    forecast questions only. Incident mode never constructs any coordinator — zero agents
    on this path.
*   `api/index.py` (Vercel) — incident mode is out of scope there (read-only filesystem vs
    `PersistentClient` + model cache); the serverless path returns a clean 501 for the
    incident routes rather than a silent 404.
*   `main.py` — `run_web` startup adds the incidents analogue of the RAG auto-build:
    ensure the collection exists / rebuild from JSON before serving. `analyze_async` /
    `analyze` check the flag before any coordinator construction (the debate pipeline's
    first act is a Tavily call; a misrouted paste must not burn search quota — incident
    mode's own searches are deliberate and capped).

### Integration points (existing code, unchanged behavior)

*   `config.py` — new keys following the existing env-var pattern, resolved to absolute
    paths anchored at the package root: `incidents_data_path`, `incidents_collection`,
    `incident_weak_threshold` (default 0.45 until calibrated), `debate_enabled` (default
    false), `max_research_rounds` (1), `questions_per_round` (5).
*   `rag/builder.py` — `build_all()` gains `build_incidents()` (read JSON corpus, embed
    `summary_embed`, upsert into `incidents` with cosine space) so the Docker image
    pre-bakes the collection the same way it pre-bakes the wisdom collections.
*   `Dockerfile` — builder stage sets `FASTEMBED_CACHE_PATH` and copies the model cache
    (~130 MB) into the runtime image; a runtime cold start must not re-download the
    embedding model, because the matcher's primary signal is that embedding.
*   `core/llm_client.py` — used as-is via the existing async client for the one extraction
    call and outcome mapping; the shared RPM limiter is unaffected at incident volumes. A
    known pre-existing bug (per-request `asyncio.run()` rebuilding the limiter in the
    threaded server) is noted; incident mode must not rely on cross-request limiting.
*   `search/web.py` — the research loop's only search dependency. A new thin structured
    function (`search_structured()`) returns a list of `{title, url, snippet, date}`
    dicts for a single query; `research.py` calls that, never `search_news()`. Queries are
    deduplicated per string within a paste, at most ten per paste (two rounds × five
    questions). `search_news()` is left untouched for the debate path.
*   Web UI (`api/static/`) — incident results render in a full-height overlay (the current
    350px verdict aside cannot host the output contract), with a multiline paste box, the
    mode selector (Incident | Debate; the Debate option inert while the flag is off), an
    extracted-fields review/edit state before save, `tag · source` rendering on every
    claim, both timelines, and the research Q&A with its tags.

### Scoring and explanation mechanics

*   `scoring.py` is deterministic given `(cosine, card, candidate)`: weights sum to 1.0
    (`0.25 cosine, 0.20 trigger_type, 0.15 roles-Jaccard, 0.10 constraint-Jaccard,
    0.10 escalation-Jaccard, 0.05 resolution, 0.05 tempo, 0.05 exit_authority,
    0.05 outcome-Jaccard`); `WEIGHTS_VERSION` is echoed in responses; a weight change
    forces a same-commit fixture update. outcome-Jaccard compares typed fields only —
    `resolution`, `succession`, `constraint_types` — never free text.
*   The mechanically generated explanations live in `scoring.py` itself: why-matches
    (shared/equal typed fields, weighted by their scoring contribution) and
    where-it-breaks (mismatched or missing fields) derive directly from the scorer's
    per-component output. There is no narrative LLM call anywhere in incident mode — the
    former optional gloss is cut.
*   Tiers: strong = S ≥ `incident_weak_threshold`; weak = S below the threshold among the
    retrieved top-5; no-match = zero strong matches. The no-match state is also gap type
    4 — gap type 4 raises no search and no question; it renders as a "new shape"
    notice plus the one field that would disambiguate, and does not count toward the
    two-round cap. The panel shows weak candidates as context only, and the loop raises
    the other gap types questions.
*   Base rate: computed by `scoring.py` over the strong tier (or over cards sharing the
    paste's trigger_type when the strong tier is empty) — the corpus frequency of the
    structural signature and the distribution of resolutions among those cards, rendered
    with explicit counts ("4 of 30 recorded cases; 3 resigned, 1 ongoing"). Small
    denominators are stated, never hidden.
*   Silence line: assembled by `match.py` from card state and loop results — empty card
    fields, claims tagged below `documented`, and every gap that closed as "no source
    available". One line, dated, naming what the record does not establish.
*   Empty-corpus behavior: `Jaccard(∅, ·) = 0`; an empty corpus returns
    `{"matches": [], "corpus_size": 0}` so the UI can say "no records yet" —
    distinguishable from "no match".

### Worked example (scoring, fixture basis)

Exact-string matching after the stated canonicalization rule; all extracted list members
participate; no near-role equivalences in v1. cosine = `1 − distance` (bge-small assumed).

**Nvidia 2026-11-12 vs Petraeus 2012**, full arithmetic (cosine 0.55 assumed on the
structural-template embedding):

| Component | Values | Contribution |
|---|---|---|
| cosine | template cosine 0.55 | 0.25 × 0.55 = **0.138** |
| trigger_type | personal_conduct = personal_conduct | **0.20** |
| roles Jaccard | {CEO, founder, board, CFO, intel_agency} ∩ {director, intel_agency, government} = 1; union 7 → 1/7 | 0.15 × 0.143 = **0.021** |
| constraint Jaccard | {reputational, security} ∩ {legal} = ∅ | **0** |
| escalation Jaccard | {media_cycle, filing, resign_signal} ∩ {inquiry, resign_signal} = 1; union 4 → 1/4 | 0.10 × 0.25 = **0.025** |
| resolution | resignation = resignation | **0.05** |
| tempo | days vs weeks | **0** |
| exit_authority | board vs self | **0** |
| outcome | none recorded yet | **0** |
| **S** | | **≈ 0.43 — flagged weak** |

That result is the demo working: an intelligence-domain government resignation is a partial
structural match for a founder-CEO corporate exit, and the score says so instead of
flattering the analogy. The other four analogs (Easterbrook/McDonald's 2019, Kalanick/Uber
2017, Strauss-Kahn/IMF 2011, Hayward/BP 2010) are corpus fixtures with the same discipline:
**pass criterion = correct ordering, not absolute scores.** The Nvidia record enters the
corpus only after the 30 curated records exist, as a held-out demo. Its provenance is
settled — a documented record whose tag statuses are fixed (see the provenance section of
the anchor case below); only its corpus position is deferred.

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
*   **Reason for Rejection**: Rejected in favor of an explicit toggle-only mode
    field (default incident); no heuristics, no guessing from question shape; toggle-only
    adds friction to every query but is explicit and correct.
    one-click override and override logging — the ambiguity band is handled by the human,
    not by a paid guess.

### Alternative I: A reduced agent panel in incident mode ("just in case")

*   **Pros**: Familiar output shape; opinion-flavored commentary alongside the matches.
*   **Cons**: Costs tokens per query on a path whose value is lookup, not deliberation;
    blurs the two modes; invites the debate pipeline's cost structure back in through a
    side door.
*   **Reason for Rejection**: Rejected by author: incident mode uses zero agents — no
    reduced panel is kept "just in case". Opinions are not research; the gap loop is.

### Alternative J: Model-decided research loop (model picks questions and when to stop)

*   **Pros**: Flexible question generation; can chase subtle lines of inquiry.
*   **Cons**: Ungrounded by construction — a model invents questions, burns searches, and
    decides it "feels finished"; unauditable; cost and stopping behavior vary per run.
*   **Reason for Rejection**: Rejected: questions come only from the four mechanical gap
    detectors and the stop rule is mechanical (nothing further closable with available
    sources, or two rounds elapsed) — the loop is grounded, never free-running.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Security & Privacy**: pasted text is user content and is stored (provisional records,
    `_raw/` spool) locally only — the corpus is not published. `POST /api/incident-match`
    and `POST /api/incident-outcome` reuse the existing `X-API-Key` handling; no new
    secrets; Groq key usage unchanged.
*   **Performance & Latency**: per fresh paste — one Groq call (45–60s explicit timeout),
    local embed/rerank (< ~1s at N≤50), and up to ten Tavily searches (~1–2s each): total
    worst-case response time on the order of tens of seconds; identical repeat pastes are
    served from the hash cache instantly. Index rebuild sub-second; one shared fastembed
    ONNX model (~130 MB cache, no torch) sized for 512 MB free-tier containers.
*   **Token overhead**: 3.5k LLM tokens hard ceiling per fresh incident (the one extraction
    call, plus at most one repair retry with the same prompt and parse error appended);
    the gap loop adds zero LLM tokens (templated questions, mechanically tagged answers);
    Tavily searches are API quota, not model tokens, capped at ten per paste; 0 LLM
    tokens and 0 searches on a repeat paste. Usage read from Groq responses and logged
    per call for the audit trail.
*   **Rollout & Rollback**: the incidents routes are additive. The flag-off
    409 "forecast mode disabled" response and the Step 0 tree cleanup are deliberate
    behavior changes, not additions — existing `/api/analyze` callers receive 409
    with "forecast mode disabled" until the flag is set. Rollback = remove the route entries and the `incidents/`
    imports; the JSON corpus is untouched. No migrations in v1; an enum rename would
    require a one-line migration plus reindex.

## Known Risks (the three weakest points)

1.  **Fresh-paste extraction still poisons the provisional corpus.** The curated 30 are
    safe (hand-authored), but every auto-extracted provisional record carries model error
    into future matches. Confirm-before-save, curated-first matching, and promote/prune
    reduce but do not eliminate it; one bad `trigger_type` on a promoted record propagates
    silently until a human notices a bad match.
2.  **Corpus selection bias and circular validation.** "Settled cases with citable
    filings" means famous, documented, mostly Western incidents; the matcher looks sharp
    exactly there and fails quietly elsewhere. And the corpus curator designed the schema
    around the Nvidia case — the held-out run shows the system retrieving what was curated
    for it. Partial fix: commit the 30-title corpus list *before* any scoring design is
    finalized; treat Nvidia as demo, not validation — its tag status is settled
    (documented), so the deferral applies to its corpus position only.
3.  **The sharpening loop's payoff is small and deferred.** The `outcomeJ` term is 0.05 of
    S — real but nearly invisible — and it requires manual return visits. The design pays
    outcomes out immediately in the UI ("what happened next" renders the moment they're
    recorded), but if the user stops pasting outcomes the loop is decorative; hence the
    freeze trigger in the implementation plan.
4.  **Research answers are only as good as the search snippet.** Mechanical tagging of
    search results cannot judge credibility, so every research answer is capped at
    `reported_unconfirmed` with its URL; a wrong or low-quality snippet can enter the card
    as a tagged-but-weak claim. Mitigations: the snippet's source renders next to the tag,
    the silence line names what remains unestablished, and artifact attachment is the only
    path to `documented`. The templated questions also read stiff — accepted, because
    question stiffness is cheap and model-invented questions are ungrounded.

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
*   **Model-assisted contradiction detection**: v1 detects contradictions mechanically only
    (conflicting dates, conflicting numbers, or mutually exclusive enum values for the same
    event); later versions may add model-judged contradiction detection — only with
    citations and the same grounded-question discipline.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

### Build sequence

**Step 0 is a hard precondition gate**: no `incidents/` code is written until the tree is
single-copy. Then four phases, in this order: (1) cards and schema, (2) scoring,
(3) endpoint and panel, (4) the gap loop last. File numbering is global; each file notes
its phase.

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

*   **Type / Scope**: Docstring fix only (substantive edit comes in Phase 1).
*   **Proposed Changes**: Correct stale `python -m veritas.rag.builder` to
    `python -m vg.rag.builder`.

#### 9. `.env.example` (Modify)

*   **Type / Scope**: Config template.
*   **Proposed Changes**: Fix the stale "MUDDL API Keys" header.

#### Phase 1 — Cards and schema

#### 10. `incidents/__init__.py` (Create)

*   **Type / Scope**: Python package marker.
*   **Proposed Changes**: Re-export the public surface (schema types, store functions,
    match orchestration entry). Imports from the rest of the repo are limited to
    `vg.config`, `vg.core.llm_client`, and `vg.search.web`.

#### 11. `incidents/schema.py` (Create)

*   **Type / Scope**: Card dataclass + validation (stdlib only).
*   **Proposed Changes**: Incident card dataclass, strict enums and closed vocabularies
    (folds the former constants module), the mechanical tag cascade, JSON round-trip and
    validation (bad enum/field → `ValueError` listing fields), the load-time provenance
    downgrade (a `documented` claim whose excerpt file is absent under
    `data/incidents/<id>/sources/` loads as `reported_unconfirmed`), the fixed
    `summary_embed` template over canonical fields only (model never writes it; template
    change ⇒ full re-embed), and claim ids `c1…cn` in list order, local to the card.

#### 12. `incidents/store.py` (Create)

*   **Type / Scope**: Persistence layer (JSON cards + Chroma index + embedding).
*   **Proposed Changes**: Sole mutation point. `threading.Lock` around every JSON+Chroma
    mutation; atomic writes (temp file + `os.replace`); `rebuild_index()` (read all JSON,
    upsert by `incident_id`; sub-second at N≤50); `record_hash` (sha256) in Chroma
    metadata; count/hash drift check at server start and per query against top-20
    candidates; collection created with `hnsw:space='cosine'`; one encode/decode pair for
    the `;`-joined list metadata; paste-hash repeat cache. Folds the former embedder
    module: one shared lazily-created fastembed `TextEmbedding`
    (`BAAI/bge-small-en-v1.5`) used for both index writes and query embedding;
    unavailability raises a typed error → 503 upstream, never an empty result set (does
    not inherit the repo's silent-`[]` retriever pattern).

#### 13. `data/incidents/README.md` (Create)

*   **Type / Scope**: Corpus authoring guide.
*   **Proposed Changes**: Template card (YAML/JSON, one per incident):
    `{incident_id, title, status: "curated", date, recorded_at, actors, actor_roles,
    sector, geography, trigger, trigger_type, constraint_types, legal_outcome,
    escalation_vector, tempo, exit_authority, succession, timeline, resolution, outcome,
    claims, sources, summary_embed}`. Authoring rules: cards are hand-authored JSON
    (extractor not involved), outcomes pre-filled for settled cases, `documented` claims
    carry excerpt refs under `data/incidents/<id>/sources/`, claim ids `c1…cn` in list
    order. The 30-title corpus list is committed as
    `data/incidents/_corpus_list.md` before any scoring code exists; the list contains
    titles only (one per line), no descriptions. Nvidia is excluded from the 30; it enters
    as held-out demo #31 after weak-floor calibration.

#### 14. `data/incidents/*.json` × 30 (Create — user-authored)

*   **Type / Scope**: Curated corpus cards.
*   **Proposed Changes**: Authored by the curator, not by this implementation; outcomes
    pre-filled; claims tagged with real source refs. The Nvidia card is **excluded** — it
    enters as held-out demo #31 after weak-floor calibration. Test fixtures for entry 20
    use synthetic cards (not the Nvidia card) authored in `tests/fixtures/`, avoiding the
    exclusion conflict.

#### 15. `config.py` (Modify)

*   **Type / Scope**: Configuration.
*   **Proposed Changes**: New keys following the existing env-var pattern, resolved to
    absolute paths anchored at the package root (never CWD-relative):
    *   `incidents_data_path` — env var `VG_INCIDENTS_DATA_PATH`, default
        `<package_root>/data/incidents`, resolved via
        `Path(__file__).resolve().parent.parent / value` if relative.
    *   `incidents_collection` — env var `VG_INCIDENTS_COLLECTION`, default `"incidents"`.
    *   `incident_weak_threshold` — env var `VG_INCIDENT_WEAK_THRESHOLD`, default `0.45`.
    *   `debate_enabled` — env var `VG_DEBATE_ENABLED`, default `false`.
    *   `max_research_rounds` — env var `VG_MAX_RESEARCH_ROUNDS`, default `1`. The second round is reserved for when card write-back exists (not in v1).
    *   `questions_per_round` — env var `VG_QUESTIONS_PER_ROUND`, default `5`.
    Placed in the `Config` dataclass after the existing debate section; read through
    `get_config()` via `os.getenv` with the defaults above. `Path` resolution happens at
    import time.

#### 16. `rag/builder.py` (Modify)

*   **Type / Scope**: Index builder.
*   **Proposed Changes**: `build_incidents()` added to `build_all()` — signature
    `build_incidents(data_path: str, collection_name: str, embedder)` reads
    `data_path/*.json`, embeds each card's `summary_embed`, upserts into the `incidents`
    Chroma collection with metadata `{incident_id, status, record_hash, WEIGHTS_VERSION,
    TEMPLATE_VERSION}`, ID = `incident_id`, re-runs are upsert-by-`incident_id`
    (delete-first not required). Called from `build_all()` after the personality
    collections, before the function returns. (Also corrects the stale
    `python -m veritas.rag.builder` docstring.)

#### 17. `Dockerfile` (Modify)

*   **Type / Scope**: Build configuration.
*   **Proposed Changes**: Builder stage sets `ENV FASTEMBED_CACHE_PATH=/tmp/fastembed_cache`
    and adds `COPY --from=builder /tmp/fastembed_cache /tmp/fastembed_cache` to the
    runtime stage, placed after the existing `COPY` of `chroma_db` and before `CMD`.
    Runtime image contains the pre-baked `incidents` collection (built by
    `build_incidents()`) and the fastembed model cache (~130 MB); a cold start does not
    re-download the embedding model.

#### 18. `tests/test_incident_schema.py` (Create)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: JSON round-trip; enum validation errors; the mechanical tag
    cascade; the downgrade rule in both directions (excerpt present → `documented`,
    absent → `reported_unconfirmed`); `summary_embed` template determinism. Offline;
    follows the existing `tests/` sys.path shim convention.

#### Phase 2 — Scoring

#### 19. `incidents/scoring.py` (Create)

*   **Type / Scope**: Pure scoring functions (no I/O, no LLM, no Chroma imports).
*   **Proposed Changes**: Score given `(cosine, card, candidate)` with cosine injected as
    a parameter; per-component contributions returned with the score; `Jaccard(∅, ·) = 0`;
    tiers — strong/weak against `incident_weak_threshold`, zero strong ⇒ the no-match
    state; the hand-set `WEIGHTS` dict with `WEIGHTS_VERSION = 1` (folds the former
    constants weights); mechanically generated why-matches/where-it-breaks from
    per-component diffs; base-rate computation over the strong tier (trigger_type-sharing
    cards as fallback) with explicit counts; `calibrate_weak_floor()` via leave-one-out
    self-matching (run once post-corpus).

#### 20. `tests/test_incident_scoring.py` (Create)

*   **Type / Scope**: Golden fixture tests.
*   **Proposed Changes**: Synthetic card fixtures in `tests/fixtures/` (one Nvidia-analog
    card plus five analogs, not the excluded Nvidia card); cosine stubbed; per-component
    contributions asserted within ±0.01; one test asserts weights sum to 1.0; base-rate
    counts asserted on the fixtures; **pass criterion = correct top-5 ordering, never
    absolute scores**.

#### Phase 3 — Endpoint and panel

#### 21. `incidents/match.py` (Create)

*   **Type / Scope**: Orchestration (extract → score → respond; gap-loop integration
    lands in Phase 4).
*   **Proposed Changes**: Card extraction — the one small-model call (async `allam-2-7b`,
    JSON mode `response_format={"type":"json_object"}`, explicit 45–60s timeout, one
    repair retry, tolerant-parse fallback; paste cap 4,000 chars; English-only;
    multi-incident paste → extract the dominant incident or reject; injectable extractor
    so tests never hit Groq; failure → `needs_manual_entry`, raw paste spooled to
    `data/incidents/_raw/`, no partial card written). Then: ensure index → embed query →
    top-20 by `1 − distance` → scoring.py rerank/tiers → mechanical bullets → base rate →
    silence line (from card state at this phase) → response with `retrieval_debug` and the
    `as_of` date. The zero-token structural mode gate lives here as a small function
    (folds the former router module), run before any coordinator construction. Also
    `extract_outcome()` (same call pattern) for outcome recording.

#### 22. `api/server.py` (Modify)

*   **Type / Scope**: Web server.
*   **Proposed Changes**: `do_POST` hardcoded comparison → dispatch table keyed by path:
    `{"/api/analyze": _handle_analyze, "/api/incident-match": _handle_incident_match,
    "/api/incident-outcome": _handle_incident_outcome}`. Handler signatures:
    `_handle_incident_match(body: dict) → dict` and
    `_handle_incident_outcome(body: dict) → dict`, where `body` is the JSON-parsed POST
    body. Request body for `/api/incident-match`: `{paste: str, mode: str}` where `mode`
    defaults to `"incident"` when absent. Response body for `/api/incident-match`:
    `{matches: [{id, score, components, cosine, card}], retrieval_debug: {...},
    base_rate: {...}, silence_line: str, as_of: str, loop_audit: [...]}`. Request body for
    `/api/incident-outcome`: `{incident_id: str, outcome_text: str}`. Response body:
    `{status: str}`. Incident routes reuse the existing `X-API-Key` handling — the key is
    required for both routes (Groq key for extraction on incident-match, Groq key for
    outcome mapping on incident-outcome). Typed failures: embedder down → 503 with reason;
    invalid extraction → `needs_manual_entry` with the paste spooled; search unavailable →
    "no source available" per question and a completed response. `POST /api/analyze`
    gated on `debate_enabled` — flag off → return 409 with "forecast mode disabled"
    without constructing a coordinator; flag on → unchanged behavior. GET serving
    untouched. No new endpoints beyond the two listed.

#### 23. `main.py` (Modify)

*   **Type / Scope**: Entry point.
*   **Proposed Changes**: `run_web` startup gains the incidents analogue of the RAG
    auto-build: ensure the `incidents` collection exists / rebuild from JSON before
    serving (the RAG check only fires when `chroma.sqlite3` is absent, which never happens
    in the baked image). `analyze_async` / `analyze` check `debate_enabled` before any
    coordinator construction.

#### 24. `api/index.py` (Modify)

*   **Type / Scope**: Vercel serverless handler.
*   **Proposed Changes**: Both incident routes return a clean 501 — Vercel is out of scope
    for incident mode (read-only filesystem vs `PersistentClient` + model cache).

#### 25. `api/static/index.html` (Modify)

*   **Type / Scope**: Web UI.
*   **Proposed Changes**: Mode selector (Incident | Debate; the Debate option hidden while
    the flag is off); multiline paste box for incident mode (with the 4,000-character
    truncation notice); full-height overlay panel replacing the 350px aside; extracted-fields
    review/edit state between extract and save. The match output contract rendered by the
    panel: JSON shape `{matches: [{id, score, card: {trigger_type, constraint_types,
    escalation_vector, tempo, exit_authority, succession, sector, resolution,
    legal_outcome, outcome}}, retrieval_debug: {extracted_record, corpus_version,
    weights_version, weak_threshold, excluded_provisional_count,
    candidates:[{id, score, components, cosine}]}], base_rate: {count, distribution},
    silence_line: str, as_of: str, loop_audit: [{question, gap_type, query,
    closed: bool, source: str|null}]}`. Panel states: idle / extracting / reviewing /
    matching / complete / error (503, needs_manual_entry, no source available per question).
    Styles live where the file already carries them.

#### 26. `api/static/app.js` (Modify)

*   **Type / Scope**: Web UI logic.
*   **Proposed Changes**: Panel flow — extract → review → confirm → render; state machine
    with transitions: `idle → extracting → reviewing → matching → complete`; on
    `needs_manual_entry` return to `reviewing` with the raw paste shown; on 503 show
    "embedder unavailable" and stop. Render: strong/weak/no-match tiers with top-3-equivalent
    emphasis (the strong tier visually dominant, ordering labeled as heuristic), base rate
    with explicit counts, the silence line, the "as of <date>" stamp, `tag · source` on
    every claim, both timelines, closest-match outcome, the "no card in memory matches
    this pattern yet" state, and the research Q&A with its tags and "no source available"
    markers. Event flow: paste submitted → POST `/api/incident-match` → poll until
    complete → render panel. Error handling: 503 → show error banner, no retry; 409 → hide
    Debate option permanently; "no source available" → render question with marker, no
    retry. One-click mode override writes `mode` to localStorage; repeat-paste cache
    indicator shows when a cached result is served. No new endpoints consumed.

#### 27. `incidents/store.py` (Modify)

*   **Type / Scope**: Persistence layer.
*   **Proposed Changes**: `record_outcome()` — typed outcome fields via
    `match.extract_outcome`, JSON-only update (**no re-embed**: `summary_embed` excludes
    outcome fields), `record_hash` refresh. Promote/prune = direct JSON status edit
    (documented; no endpoint — see cuts). Under the same lock as every other mutation.
    Triage trigger: if no outcomes have been recorded after N weeks of use, freeze the
    sharpening loop instead of building more around it.

#### 28. `tests/test_incident_match.py` (Create)

*   **Type / Scope**: Integration tests (no network).
*   **Proposed Changes**: Stub extractor + fake embedder + override
    `config.chroma_db_path` → tmp dir (no `VG_CHROMA_PATH` env var; the config key is
    `incidents_data_path`, resolved absolute); empty-corpus behavior; `retrieval_debug`
    and `as_of` shape; hash-mismatch triggers rebuild; paste-cap and
    `needs_manual_entry` paths; the 409 "forecast mode disabled" response; no fixture
    touches Groq. Extractor stub injects via the `extract_card(paste, extractor=...)`
    parameter; embedder stub returns fixed cosine values.

#### 29. `tests/test_incident_outcome.py` (Create)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: Outcome write path — no re-embed, hash refresh, the outcome
    renders in subsequent match payloads; a failed extraction writes nothing.

#### Phase 4 — The gap loop (last)

#### 30. `incidents/gaps.py` (Create)

*   **Type / Scope**: Gap detection (zero model calls).
*   **Proposed Changes**: The four detectors, all mechanical: (1) empty card fields among
    the match-relevant set (trigger_type, constraint_types, escalation_vector, tempo,
    exit_authority, succession, resolution, legal_outcome, outcome); (2) expected evidence
    missing — a per-trigger_type profile in this module (e.g., personal_conduct should
    contain a filing or board statement; market_shock a market reaction); the card holds
    no claim or timeline item of an expected kind → gap; (3) claim contradiction,
    mechanical only in v1 — same-event claims with conflicting dates, conflicting numbers,
    or mutually exclusive enum values (e.g., resolution resignation vs ongoing); (4) no
    card in memory matching at all = zero strong-tier matches. Deterministic ranking
    (empty fields → contradictions → missing expected evidence → no-match) capped at
    `questions_per_round`; each gap emits a templated question text, a search query, and
    the closure target it can fill.

#### 31. `incidents/research.py` (Create)

*   **Type / Scope**: Grounded research loop.
*   **Proposed Changes**: One search per question via `vg.search.web.search_news`; queries
    deduplicated per string within a paste. A usable result (URL + usable snippet) →
    written back through existing card fields: claim text from the snippet, a `sources`
    entry with the URL and date, tag `reported_unconfirmed` — the cascade ceiling, never
    `documented` without an attached artifact — and the gap's target field filled where
    derivable. No usable result → the question is marked "no source available" and stays
    open. Round 2 runs only if round-1 write-backs exposed new closable gaps. Mechanical
    stop rule: stop when no open gap remains, when all remaining open gaps have returned
    "no source available", or when `max_research_rounds` (1) is reached — never on a
    model's judgement (no model participates in the loop).

#### 32. `incidents/match.py` (Modify)

*   **Type / Scope**: Orchestration.
*   **Proposed Changes**: Loop integration between first score and response: gaps →
    questions → research → write-back → re-embed (filled fields change `summary_embed`;
    local and free) → re-score → final tiers / base rate / silence line; the loop audit
    (questions, gap types, queries, closed/no-source status) added to the response.

#### 33. `tests/test_incident_gaps.py` (Create)

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: Detector table tests — each gap type triggered by a fixture
    card; deterministic ranking and the cap; zero-model-call assertions; contradiction
    fixtures (conflicting dates, conflicting numbers, exclusive enum values); no-match =
    zero strong matches.

#### 34. `tests/test_incident_research.py` (Create)

*   **Type / Scope**: Unit tests (stubbed search).
*   **Proposed Changes**: Exactly one search per question; per-query dedupe; write-back
    claims tagged `reported_unconfirmed` with URL sources (ceiling test); the "no source
    available" path; round 2 only on newly exposed closable gaps; the stop rule (no gaps /
    all no-source / two-round cap); re-embed + re-score after fills. No fixture touches
    Groq or the real Tavily endpoint.

### Explicit cuts (considered, not built)

*   No separate agent modules — no `constants.py`, `embedder.py`, `ingest.py`,
    `explain.py`, or `router.py` files; their contents fold into `schema.py` /
    `scoring.py` (constants, explanations), `store.py` (embedder), and `match.py`
    (ingestion, routing) to keep the package at six files.
*   No narrative gloss — no optional small-model "explain" call anywhere in incident
    mode; explanations are the scorer's mechanical bullets, zero tokens.
*   No reduced agent panel in incident mode "just in case" — the incident path uses
    zero agents; the full debate pipeline stays parked behind `debate_enabled`
    (default off) for forecast questions only.
*   No model-decided research loop — no model-invented questions, no model-decided
    stopping; questions come only from the four mechanical gap detectors, and the stop
    rule is mechanical (nothing further closable, all remaining gaps no-source, or two
    rounds elapsed).
*   No new card fields for the loop — research answers write back through existing
    fields only; the loop audit rides in the API response, never in the card.
*   No `/api/incident-promote` endpoint — promote/prune is a direct JSON edit; the index
    rebuilds on hash drift.
*   No separate calibration CLI — `calibrate_weak_floor()` is a tested function run once
    after the corpus exists.
*   No capabilities/mode-discovery endpoint — the panel reads `debate_enabled` from
    config and renders the Debate option inert when the flag is off; nothing to fetch.
*   No incident implementation in `api/index.py` — 501 only.

### Verification Plan

*   **Compilation/Build**: `python -m compileall incidents/` plus an import smoke
    (`python -c "import vg.main, vg.api.server"`). No linter is configured in the repo;
    nothing new is introduced.
*   **Unit Tests**: `pytest tests/` — every new suite runs offline: stub extractor and
    fake embedder with `VG_CHROMA_PATH` → tmp dir; the gap-loop suites run with
    **stubbed search** — no fixture touches Groq or the real Tavily endpoint. The golden
    scoring suite (file 20) is the correctness gate with the ordering-only criterion;
    file 18 covers the tag cascade and the downgrade rule in both directions. Note:
    pytest is a dev-only dependency (`requirements.txt` does not declare it) — record it
    in a dev-requirements note rather than adding it to runtime dependencies.
*   **Gap-loop gate (files 33–34)**: exactly one search per question; per-query
    dedupe within a paste; write-back claims tagged `reported_unconfirmed` with URL
    sources (the cascade ceiling — never `documented` without an attached artifact);
    the "no source available" path leaves the gap open and completes the response;
    round 2 runs only on newly exposed closable gaps; the two-round cap; and
    zero-model-call assertions on `gaps.py` and `research.py` — the loop consumes no
    LLM tokens by construction, and the tests prove it.
*   **Test Coverage Requirement**: every `incidents/` module carries its own suite; the
    scorer's per-component arithmetic is asserted to ±0.01, not just final scores.
*   **Debate flag, both states**: flag off → `/api/analyze` returns 409 with
    "forecast mode disabled" and no coordinator is constructed (asserted by counting
    constructor calls in the test); flag on → unchanged debate behavior; the incident
    routes never construct a coordinator in either state.
*   **E2E/Manual**: curl smoke of extract → review → confirm → loop against a running
    server; typed failures exercised (oversized paste, unparseable paste, embedder path
    missing → 503, search unavailable → "no source available" per question with the
    response still completing); Docker build verified to contain the `incidents`
    collection and the model cache, with a cold start that does not re-download; token
    audit from Groq response usage (≤ ~2.3k LLM tokens fresh — all from the one
    extraction call, 0 from the gap loop, 0 on a repeat paste) plus a search-quota audit
    (≤ 10 Tavily searches per fresh paste, 0 on repeat); the Nvidia held-out demo runs
    only after the 30-card corpus exists, with observed ordering recorded; committing
    the excerpt file flips the anchor case's claims to `documented` (downgrade rule
    verified live).

--------------------------------------------------------------------------------

*Drafted with EGM*
