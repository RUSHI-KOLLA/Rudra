# Incident Memory: Structural Match Against Recorded History (v2)

* **Author:** Rushi
* **Date:** 2026-11-17
* **Status:** Brainstorm brief — revised after 7-lens Goldfish review (design, codebase-details, zoom-out, comprehension, implementation-readiness, structural, inventive-catalyst)

## Overview

A second analysis mode for VG. The user pastes a live news incident; the system extracts a
structured incident record, embeds it, and finds the most structurally similar incidents in a
hand-curated history (30–50 records at launch). Output per incident: top-5 matches with
"why it matches / where it breaks," every claim tagged by provenance, two timelines, and what
happened next in the closest match. Every pasted incident can be saved as a provisional record
with one confirmation, so the corpus grows as a side effect of use. Opinion and forecast
questions stay on the 10-agent debate pipeline; incident questions route to the matcher.

Revised token position (reviewer-adopted): match explanations are generated **mechanically**
from typed-field diffs — zero tokens, always consistent with the computed score. The LLM
appears once per fresh paste (extraction) and optionally as a narrative gloss. Steady state
drops from ~5.4k to **~2.3k tokens per fresh incident; 0 on repeat via paste-hash caching**.

All processing is local (ChromaDB + fastembed) except that one extraction call. Free tier,
plain Python, built beside the debate pipeline — no rewrite. **Correction from review:** the
repo's embedding stack is fastembed (ONNX) + `BAAI/bge-small-en-v1.5` — there is no
sentence-transformers and no torch in the repo, and adding them (~2 GB) would break the slim
Docker image and Koyeb's 512 MB tier. v1 brief said MiniLM; that was wrong.

## Provenance status of the anchor case

The Nvidia case is **documented**. The author holds two primary artifacts, with excerpts
designated for `data/incidents/nvidia_2026/sources/nvidia_2026_sources.md`:

- SEC Form 8-K, Item 5.02 — event date 2026-11-11, filed 2026-11-12, accession
  `0001045810-26-000082`
- NVIDIA investor press release, dated 2026-11-12

Tag split, stated explicitly:

- `documented` — resignation as President, CEO, and board member effective immediately;
  Colette Kress appointed interim CEO; Harvey C. Jones appointed Chair; a 33-year tenure
  (press release wording).
- `reported_unconfirmed` — the affairs; the intelligence assessment that a relationship
  partner was a foreign asset; the 13% share drop.
- The 8-K gives **no reason** for the resignation. Every rendering of this record must say
  so plainly: the primary document is silent on cause, and that silence is the hinge the
  whole explanatory chain turns on. The matcher must not fill it with press narrative.

A classified intelligence assessment can never reach `documented` — that note is UI copy,
not an ingest rule. The excerpt file is the artifact anchor: until it is committed to the
tree, the load-time rule (see schema, Deliverables §1) keeps the affected claims at
`reported_unconfirmed`.

## Goldfish synthesis (deduplicated across 7 reviewers)

### Consensus blockers — all adopted

1. **Embedding stack** (5 reviewers, file:line evidence). Use the existing fastembed +
   `BAAI/bge-small-en-v1.5` stack; forbid sentence-transformers/torch. Chroma similarity =
   `1 − distance` on a collection created with `hnsw:space='cosine'`; do not reuse
   `rag/hybrid_retriever.py`, which converts cosine distances as if L2 (a live repo bug the
   new code must not inherit). The worked example's "cosine 0.61" restated as an assumed
   bge-small value.
2. **Worked-example arithmetic was wrong** (3 reviewers independently). The Petraeus
   role-Jaccard silently filtered list members per component; no consistent rule reproduces
   the v1 table, and 0.72 is unreachable (would need cosine ≥ 0.93). v2 states the
   canonicalization rule once, computes every term, and lands at **S ≈ 0.43** — below the
   weak floor, which is itself the honest demonstration that a intelligence-domain CEO exit
   is only a partial structural match. Pass criterion for fixtures = correct top-5
   *ordering*, never absolute scores.
3. **Module boundary** (structural, blocker). Not `core/incidents.py` — `core/` is already a
   12-module accretion zone. Use a top-level `incidents/` package:
   `schema.py` (dataclass, enums, JSON round-trip), `scoring.py` (pure functions, no I/O),
   `store.py` (JSON + Chroma, sole mutation point, `threading.Lock`, atomic writes),
   `ingest.py` (the one extraction call; imports only `vg.core.llm_client`),
   `embedder.py` (fastembed wrapper), `match.py` (orchestration). Shared surface with the
   debate pipeline: `config.py` + `core/llm_client.py` and nothing else.
4. **The repo already owns three of these subsystems** (zoom-out, blocker):
   `core/upset_patterns.py` (curated historical records with structural fields + scoring,
   injected into debate context), `core/feedback.py` (manual outcome recording), and the
   fastembed/Chroma/rerank stack in `rag/` + `core/optimization.py`. The genuinely new parts
   are the incident-shaped schema and typed-field scoring. **Open decision for the author**
   (see Key Decisions): attach the new corpus to the existing pattern-grounding path, or
   keep a dedicated mode + panel.
5. **Deployment** (codebase-details + implementation-readiness): Dockerfile pre-bakes only
   the wisdom collections — add `build_incidents()` to `build_all()` plus a startup check
   for collection existence. Vercel cannot host incident mode (read-only FS vs
   `PersistentClient` + model downloads); declare Docker/Koyeb the only incident targets,
   serverless path returns 501. Set `FASTEMBED_CACHE_PATH` in the builder stage and copy the
   model cache (~130 MB) into the runtime — otherwise the matcher's primary signal
   re-downloads on every cold start.
6. **Corpus growth had no mechanism** (inventive-catalyst + zoom-out, convergent). Every
   pasted incident is saved as a `provisional` record behind the existing extract-confirm
   step; curation becomes promote/prune over the queue, not authoring sessions. Matching
   prefers `curated` records; dedupe on paste hash. A paste matching nothing is the coverage
   hole revealing itself — exactly the record worth keeping.

### Corrections to v1 deliverables (all adopted)

- **Schema additions** (design): `tempo` (hours|days|weeks|months), `exit_authority`
  (self|board|investors|court|regulator|electorate), `succession`
  (internal|external|contested|unknown) — all three appeared in v1's "where it breaks" lines
  with no field behind them. Plus (comprehension): `outcome` gets typed `actors` +
  `constraint_type` (v1 scored Jaccard over fields that didn't exist);
  `claims[]` gets `supports: list[claim_id]`; `constraint_type` becomes a list with a stated
  precedence (legal > regulatory > market > reputational > security); `resolution` extended
  (conviction, bankruptcy, dissolution, grounding) or primary-first list; `status:
  curated|provisional`.
- **`summary_80w` composition** (design + comprehension, convergent): produced by one fixed
  Python template over canonical fields only — `{trigger_type}. {actor_roles}. {constraint_
  types}. {escalation}. {resolution}. {sector}. {tempo}. {succession}.` — never by the model,
  never including the free-prose `trigger` (display-only; it would reward wording similarity,
  the exact failure the concept is named against). Template change ⇒ full re-embed; recording
  an outcome ⇒ JSON update only, **no re-embed** (v1's re-embed step was a no-op).
- **Scoring v2 weights** (cosine demoted per 3 reviewers): cosine 0.25, trigger_type 0.20,
  actor_roles Jaccard 0.15, constraint Jaccard 0.10, escalation Jaccard 0.10, resolution
  0.05, tempo 0.05, exit_authority 0.05, outcome Jaccard 0.05 (typed outcome fields; 0 until
  outcomes exist). `WEIGHTS_VERSION = 1` echoed in responses; one-line test asserts the sum.
  Golden pytest (`tests/test_incident_scoring.py`): cosine injected, per-component
  contributions asserted ±0.01.
- **Claim tags: precedence cascade** (design + comprehension) settles decidability:
  1. forward-looking/hypothetical → `speculative`; 2. primary source directly cited in the
  paste **and** the document is attached → `documented`; 3. no primary document →
  `reported_unconfirmed` (redefined to also cover bare assertions — "provenance stops short
  of a primary document"); 4. residual conclusions from other claims → `inferred`, listing
  ids in `supports`. Spelling is `reported_unconfirmed` everywhere. Extraction rule: claims
  tagged `speculative` never supply matching-field values.
- **Top-5 honesty** (zoom-out): at N=30–50, an ordered top-5 is false precision. Keep the
  user's top-5 output but render strong/weak tiers, label ordering as heuristic in the UI,
  and return top-3-equivalent emphasis. If fewer than 3 of the top 5 clear the weak floor,
  the panel says "no close structural match in history yet" instead of producing confident
  why-it-matches text for matches that all break. Weak floor: calibrate once post-corpus by
  leave-one-out self-matching (free, auditable, not auto-reweighting); v1 guess 0.45.
- **Extraction hardening** (implementation-readiness + comprehension + structural):
  async client (the sync one returns `""` on 429 and hides failures), explicit
  `timeout_seconds=45–60`, JSON mode (`response_format={"type":"json_object"}`, already
  plumbed) + one repair retry + tolerant-parse fallback, paste cap 4,000 chars with UI
  truncation note, English-only v1, multi-incident paste → extract the dominant incident or
  reject. Failure → `needs_manual_entry`, raw paste saved to `data/incidents/_raw/`, no
  partial record ever written. `ingest_incident` takes an injectable extractor; tests never
  hit Groq.
- **Corpus authoring** (implementation-readiness + comprehension, convergent): the 30
  curated records are **authored directly as JSON files** — they are settled cases with
  citable filings, so the LLM extractor is not involved and costs 0 tokens; outcomes are
  pre-filled at authoring ("empty at ingest" applies only to live pastes). This also fixes
  v1's build-order inversion (corpus curated in Step 1, its quality gate shipping in Step 3).
- **Repeat queries** (codebase-details + comprehension): cache ingest + match + mechanical
  explanations keyed on `(sha256(paste), corpus_version)` — true 0-token repeats; a reworded
  paste costs the normal one call.
- **Router** (inventive-catalyst + comprehension, convergent): zero-token structural gate —
  question-mark/modal/question-word → debate; length + date patterns + entity density →
  incident — surfaced as a mode selector (Debate | Incident) pre-set by the guess, with a
  one-click override and override logging. Dispatch happens before any coordinator
  construction: `run_full_pipeline` fires a Tavily `search_news()` call first, so a misrouted
  paste burns search quota (a live trap codebase-details found).
- **Step 0 reconciliation** (4 reviewers, convergent): explicit file list, git-independent —
  delete `cli.py`, delete `vg-main/` (incl. `__pycache__`), delete `testapp/` (a third full
  copy), delete stray root `test_*.py` orphans, fix stale `veritas` docstrings and
  `.env.example`'s "MUDDL" header. Keep-list for `main.py` pinned: `analyze_async`,
  `analyze`, `run_web`, `_consume_option` stay; `run_cli`, `print_report`, `byok_setup`,
  argv handling go — byte-equivalent to the web-only shape already in `vg-main/main.py`.
  (One reviewer claim — "working tree is not a git repo" — was checked and is wrong; the
  reconciliation proceeds git-independent anyway, which is strictly safer.)
- **Observability** (codebase-details): `/api/incident-match` returns a `retrieval_debug`
  block — extracted-record echo, pre-rerank top-20 with raw cosines, per-component
  contributions — so a poisoned field is diagnosable without code access. All existing
  pipeline logging is `print()`; the matcher must not inherit that.
- **Server integration** (codebase-details + structural): convert `do_POST`'s hardcoded
  if-chain to table dispatch; `/api/incident-match` reuses the X-API-Key handling; failure
  contracts per endpoint (embedder down → 503 with reason, never empty results; explain
  unavailable → return scores anyway, mark explanations unavailable).
- **Paths** (structural): incidents config keys in `config.py` (`incidents_data_path`,
  `incidents_collection`, `incident_weak_threshold`), resolved absolute, never CWD-relative.
- **Naming** (codebase-details): the small model is `allam-2-7b` (7 B); token-table In/Out
  columns labeled "(stage totals)"; the debate baseline table relabeled "basic-mode
  baseline" — `main.py` actually prefers `EnhancedDebateCoordinator` (agent rounds cap at
  256 tokens, plus news-summarize and knowledge-graph calls), so the real baseline is higher.

### Adopted transforms with token consequences (inventive-catalyst)

- Mechanical explanations from typed-field diffs replace the batched explain call in the
  default path (**−3.1k tokens/incident**, and a hallucination surface). Optional
  small-model narrative gloss behind a flag, fed the diff so it can only annotate.
- `documented` = "the document is in the record" (user-attached artifact, locally extracted).
  No paid APIs; closes most of the borrowed-authority gap by making the user the source of
  record.
- Structural routing gate: zero tokens, auditable, with override.
- Ideal Final Result: steady state **zero mandatory API tokens** — routing by input shape,
  matching by local embeddings + typed fields, explanations by mechanical diffs, corpus
  growth by one click per paste — with the LLM appearing only where a human would willingly
  pay: extraction on fresh pastes, optional gloss.

## Deliverables v2

### 1. Schema — one incident record

Source of truth: `data/incidents/<incident_id>.json` (human-authored for curated records).
Chroma collection `incidents` in the existing `./chroma_db` path, `hnsw:space='cosine'` — a
derived cache with zero authority: `store.py` owns `rebuild_index()` (full rebuild is
sub-second at 50 records), stores `record_hash` (sha256 of file content) in metadata, and
rebuilds on any count/hash mismatch at server start. One encode/decode pair for the
`;`-joined list metadata.

```yaml
incident_id: str                  # deterministic: title + year; collision → ask user
title: str
status: enum                      # curated | provisional
date: date
recorded_at: date
actors: list[str]                 # people by common name, orgs by short name
actor_roles: list[str]            # CLOSED vocabulary in a constants module; one flat set
                                  # over all actors; NOT positionally aligned with actors
sector: str
geography: str
trigger: str                      # free sentence — display and gloss only, never embedded
trigger_type: enum                # personal_conduct | market_shock | regulatory |
                                  # internal_conflict | external_attack | policy_shift
                                  # (several apply → first onset cause)
constraint_types: list[enum]      # legal | regulatory | market | reputational | security
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
          recorded_at, sources}   # pre-filled for curated records; empty for live pastes
claims: list[{id, text, tag, source_ids, supports: list[claim_id]}]
  tag: enum                       # documented | reported_unconfirmed | inferred | speculative
sources: list[{id, type, ref, date}]   # ref points to a stored excerpt for documented claims
summary_embed: str                # fixed Python template over canonical fields; model never
                                  # writes it; template change ⇒ full re-embed
```

Provenance rule: for `documented` claims, `sources[].ref` points to a stored excerpt file
under `data/incidents/<id>/sources/`; at load time, a documented claim whose excerpt file is
absent is downgraded to `reported_unconfirmed`.

### 2. Scoring v2 — corrected worked example

```
S = 0.25·cosine + 0.20·trigger + 0.15·rolesJ + 0.10·constraintJ
  + 0.10·escalationJ + 0.05·resolution + 0.05·tempo
  + 0.05·exit_auth + 0.05·outcomeJ          (sums to 1.00; WEIGHTS_VERSION = 1)
```
Exact-string matching after one stated canonicalization rule; all extracted list members
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
settled — a documented record whose tag statuses are fixed (see the anchor-case section);
only its corpus position is deferred.

### 3. Claim tagging v2 — precedence cascade + artifact anchoring

Applied mechanically at ingest, in order: `speculative` → `documented` (primary source cited
**and** document attached, excerpt stored) → `reported_unconfirmed` (no primary document,
including bare assertions) → `inferred` (supports lists claim ids). Tags describe the
paste's provenance, never ground truth; rendered as `tag · source` on every claim. The
post-v1 web-verification plan shrinks to claims the user *cannot* source.

### 4. Token math v2

| Stage (incident mode) | Calls | In | Out | API tokens |
|---|---|---|---|---|
| Extract + tag (fresh paste, async small model) | 1 | ~1.6k | ~0.7k | **~2.3k** |
| Embed + retrieve + rerank + mechanical explanations | 0 | — | — | **0** |
| Outcome recording (occasional) | 1 | ~0.8k | ~0.2k | ~1.0k |
| Optional narrative gloss (off by default) | 1 | ~1.2k | ~0.5k | ~1.7k |
| Repeat paste (sha256 cache hit) | 0 | — | — | **0** |

Corpus authoring: 0 API tokens (JSON written by hand; embedding is local).
**Steady state: ~2.3k per fresh incident — down from ~5.4k in v1, and ~0 on repeats.**
Honest comparison (zoom-out): the reference point for "fewer tokens" is not only the debate
(16.5k best / 66.8k worst, basic-mode caps; the enhanced coordinator the repo actually runs
is higher) but also a corpus-free one-call analyst mode (~2–3k) — the corpus must beat that
baseline on match quality in the demo, or the second mode fails its own token test. Debate
table below retained as the *basic-mode* baseline (stage totals):

| Stage (basic debate mode) | Calls | In (est.) | Out (capped) |
|---|---|---|---|
| Shadow round (allam-2-7b) | 10 | ~11.0k | ~1.0k |
| Full debate if split (≤7 agents × ≤2 rounds) | ≤14 | ~32.2k | ~9.0k |
| Judge × 3 | 3 | ~10.5k | ~3.1k |
| Worst / converged-best | ≤27 / 11 | 53.7k / 14.5k | 13.1k / 2.0k |

### 5. Build order v2

0. **Reconcile the tree** (hard precondition, explicit list): delete `cli.py`, `vg-main/`
   (+ pycache), `testapp/`, orphaned root `test_*.py`; strip root `main.py` to the pinned
   keep-list; fix `veritas` docstrings, `.env.example`; update README/QUICKSTART (whose
   `cd vg` invocation is already broken).
1. **Schema freeze + corpus authoring**: `incidents/schema.py` + constants module; author
   30 curated JSONs directly (0 tokens, outcomes pre-filled); `store.py` with lock, atomic
   writes, `rebuild_index()`; `build_incidents()` in `build_all()` + Dockerfile pre-bake +
   `FASTEMBED_CACHE_PATH`; pytest round-trip.
2. **Match + score**: `scoring.py` (pure, cosine injected) + golden fixtures with
   ordering-only pass criterion + weak-floor calibration via leave-one-out;
   `/api/incident-match` with `retrieval_debug` and typed failure responses; table-dispatch
   `do_POST`.
3. **Panel**: full-height overlay (the current 350px aside cannot host it), multiline paste
   box, mode selector pre-set by the structural gate, extracted-fields review/edit state
   before save, mechanical why/breaks bullets + tag·source rendering, two timelines.
4. **Sharpening + growth**: `record_outcome` (JSON only, no re-embed); provisional→curated
   promote/prune flow; triage trigger — if no outcomes recorded after N weeks of use, freeze
   the loop instead of building more around it.

### 6. The three weakest points in this design (v2)

1. **Fresh-paste extraction still poisons the provisional corpus.** The curated 30 are safe
   (hand-authored), but every auto-extracted provisional record carries model error into
   future matches. Mitigations — confirm-before-save, curated-first matching, promote/prune —
   reduce but do not eliminate it; one bad `trigger_type` on a promoted record propagates
   silently until a human notices a bad match.
2. **Corpus selection bias and circular validation.** "Settled cases with citable filings"
   means famous, documented, mostly Western incidents; the matcher looks sharp exactly there
   and fails quietly elsewhere. And the corpus curator designed the schema around the Nvidia
   case — the held-out run shows the system retrieving what was curated for it. Partial
   fix: commit the 30-title corpus list *before* any scoring design exists; treat Nvidia as
   demo, not validation — its tag status is settled (documented), so the deferral applies to
   its corpus position only.
3. **The sharpening loop's payoff is small and deferred.** With typed outcome fields the
   `outcomeJ` term is 0.05 of S — real but nearly invisible — and it requires manual return
   visits. The design compensates by paying outcomes out immediately in the UI ("what
   happened next" renders the moment they're recorded), but if the user stops pasting
   outcomes the loop is decorative; hence the freeze trigger in Step 4.

## Goals vs. Non-Goals

**In-scope:** incident schema (v2 fields) + 30 hand-authored records; fastembed embedding +
typed-field scoring with mechanical explanations; `/api/incident-match` with retrieval_debug;
top-5 tiered matches with why/where-breaks; provenance tags with artifact anchoring; two
timelines + closest-match outcome; provisional-record growth; outcome recording; web panel +
structural router.

**Out-of-scope (v1):** per-claim web verification; automated collectors; weight
auto-tuning; sentence-transformers/torch; Vercel hosting of incident mode; the debate
pipeline reading incident records (unless the author adopts the component reframe below).

## Alternatives Weighed

- Embedding-only matching — rejected (v1): embeddings track topics, not structure.
- LLM-rerank of candidates — rejected: costs tokens for marginal gain at N=30–50.
- Auto-reweighting from outcomes — rejected by author: overfits a small corpus.
- **Debate-mode-only incident handling (replacing the matcher) — rejected by author:**
  opinion/forecast questions need the agent debate; incident questions need records.
- **Component reframe (zoom-out, blocker): feed the new corpus into the existing
  `upset_patterns`/pattern-grounding path instead of a second mode + panel — open decision,
  see Key Decisions.**
- Chroma-metadata-only storage — rejected: scalar metadata can't hold claims/timelines.
- Storing records only in a second-mode panel — rejected by review: the 350px aside and
  one-line input cannot host the output contract.

## Key Decisions & Staging for Next Steps

Resolved by review: fastembed/bge-small stack; `incidents/` package with fixed seams;
mechanical explanations; artifact-anchored `documented`; precedence-cascade tags; authored
(not extracted) corpus; paste-hash caching; structural router; Step-0 explicit file list;
Docker pre-bake + cache copy; Vercel out of scope for incidents; golden fixtures with
ordering-only criterion.

**Resolved by the author (2026-11-17):** dedicated second mode — `/api/incident-match` +
a dedicated panel; the corpus feeds the matcher only. The component reframe (zoom-out) is
declined; it remains a recorded fallback if the second mode proves redundant with the
pattern-grounding path in practice.

**Defaults in force unless objected:** `testapp/` is deleted in Step 0 (third divergent
copy, confirmed untracked/safe by implementation-readiness); top-5 output with strong/weak
tiers per the original requirement, falling back to top-3 emphasis if the demo shows rank
noise.

Next step per the EGM flow: `egm-draft` on this brief.
