# Zoom-Out Report — Stage 5 (Initial Zoom Out Review)

**Target:** `/home/rushi/vg/docs/designs/incident-memory.md` (1010 lines; FeatureRange 1..625, DetailedRange 626..1010)
**Preset:** Consolidated report with all review rubrics (uninterrupted full flow)
**Reviewers:** `egm-zoom-out` (applying `resources/document_standards/zoom-out-standard.md`), `egm-inventive-catalyst`
**Date:** 2026-11-18
**GoldfishContext:** none (the document contains no links; the author provided no additional context files)

## Merge notes (orchestrator)

- **Cross-reviewer overlap — one defect, two framings:** Zoom-out Finding 1 and Catalyst Finding 8 both identify the `search/web.py` contract gap (24-hour news filter, display-formatted string return, `" latest news"` suffix, silent exception re-search). Treat as a single remediation item with combined consequences: historical/expected-evidence questions return nothing, snippet parsing is fragile, and the silent re-search breaks the one-search-per-question arithmetic the verification plan asserts.
- **Related but distinct — mode gate:** Zoom-out Finding 2 (defer the zero-token structural gate while the debate flag ships off) and Catalyst Finding 4 (misroute-cost asymmetry: the incident side has no quota protection) point at the same machinery. A "defer the gate" resolution must keep Catalyst's mechanical incident-shape precondition (datable event + named actor before the loop runs) so incident-side quota protection survives regardless of when the structural gate ships.
- **Independent verification agreement:** both reviewers separately verified the same repo facts — `hybrid_retriever.py` treats cosine distance as L2, `allam-2-7b` is the configured small model, Step 0's deletion targets exist, `do_POST` hardcodes the `/api/analyze` comparison.
- **No 🔴 Blocker findings from either reviewer.** All findings are 🟡 Major or 🟢 Nit.

---

## Reviewer 1: egm-zoom-out (Skeptical Architect)

# Zoom-Out Review — Stage 5 (Initial Zoom Out Review)

**Target:** `/home/rushi/vg/docs/designs/incident-memory.md` (1010 lines, revised zero-agent version, reviewed in full)
**Standard:** `zoom-out-standard.md` | **Persona:** Skeptical Architect (Zoom Out) | **GoldfishContext:** none
**Method:** Full-document read, plus codebase verification of every cited integration point (`core/upset_patterns.py`, `search/web.py`, `rag/builder.py`, `rag/hybrid_retriever.py`, `api/server.py`, `api/index.py`, `config.py`, `main.py`, `core/llm_client.py`, `core/enhanced_debate.py`, `core/pattern_engine.py`, `cache.py`, `Dockerfile`, `requirements.txt`, `run.py`, `tests/`, static assets).

## §0 Context Sufficiency — PASS

The document defines the objective (structural match of live incidents against a recorded corpus) and the motivation (three concrete gaps: no incident memory, no provenance, debate-level cost for what is a lookup) clearly enough for a fresh reader. No context request needed.

## Standard Checklist Summary

- **Root Problem Focus (§1): PASS.** The design attacks the root cause (no structured incident store) rather than patching the debate pipeline's output, and aligns with the repo's stated philosophy (README: "minimal token consumption"). The zero-agent incident path is the correct altitude of fix for a lookup-shaped problem.
- **Simplicity & Extensibility (§2): Mostly PASS — two findings below.** The zero-agent redesign is a genuine simplification; alternatives A–J are documented with verified rejection reasons (I checked G against `requirements.txt`/`Dockerfile`, F against Chroma metadata limits, D against `core/upset_patterns.py`).
- **Anti-Weeds (§3): PASS at the document level.** The Technical Plan stays at architecture/data-flow altitude; the worked-example arithmetic is justification, not pseudocode; the Implementation Plan is file-scoped, not function-scoped. One workaround-vs-structural-fix issue below (Finding 1).
- **Leverage Existing (§4): Strong PASS with one contract gap (Finding 1).** fastembed/bge-small, ChromaDB, Groq, Tavily, `X-API-Key`, and the RAG auto-build pattern are all reused, and every reuse claim I could check in code is accurate (details at the end). G6 (zero new runtime deps) is achievable — `groq`, `tavily-python`, `chromadb`, `fastembed` are all already declared.

## Findings

### 🟡 Major — Finding 1: The research loop's data contract does not exist in `search/web.py` as designed
- **Affected Scope:** Data flow (lines ~327–338), Integration points (`search/web.py`, lines ~381–384), `incidents/research.py` spec (lines ~907–919), Target Files list (no `search/web.py` entry).
- **Simplicity Rationale:** The design says the loop consumes "URL + usable snippet" and writes back a claim text + a `sources` entry with the URL. The repo's only search function, `search_news()`, returns a **pre-formatted display string**: results truncated to 220 chars (`content[:220]`), titles/URLs interleaved into human-readable lines, plus a Tavily `include_answer` summary. It also enforces a **24-hour `from_date` news filter** and defaults to **4 results**. Consequences: (a) research.py must parse display text to recover URL/snippet — a fragile workaround where a structural fix belongs (Anti-Weeds §3); (b) for expected-evidence and historical gap questions ("was there an SEC filing?", "what was the outcome?"), the 24h filter will routinely return nothing, and the no-filter fallback only fires on *exception*, not on empty results — so legitimate gaps silently become "no source available". The Target Files list (files 1–34) never modifies `search/web.py`, so the design leaves this unresolved. **Fix is cheap and structural:** either add one small structured variant (returns `{url, snippet, date}` dicts) to `search/web.py` and add it to the plan, or state explicitly that research.py parses the string and that the loop needs a no-date-filter path. Do not leave the design claiming a contract the shared module doesn't provide.

### 🟡 Major — Finding 2: The zero-token structural mode gate is speculative machinery for a mode that ships disabled
- **Affected Scope:** CUJ 2 (lines ~151–161), `match.py` gate spec (line ~814), `app.js` override logging (line ~862), Alternatives H/I.
- **Simplicity Rationale:** `debate_enabled` defaults **off** (config, G8, Non-Goals, rollout). While the flag is off, the Debate option is inert and everything routes to incident mode anyway — the gate's pre-selection (input shape, date patterns, entity density) buys nothing a visible manual Incident | Debate selector doesn't already provide; its value materializes only if/when the flag is turned on. Meanwhile the gate adds a heuristic classifier, one-click override + override logging, and test surface to v1. This is YAGNI (§2): build the manual selector now; add the gate in the same change that first enables the debate flag. CUJ 2 should be split: manual routing at v1, gate deferred behind the flag.

### 🟡 Major — Finding 3: Boundary with `core/pattern_engine.py` is undefined — a third historical-pattern subsystem is being created silently
- **Affected Scope:** Component layout import rule (lines ~184–187), Alternative D (lines ~484–494), Future Improvements fallback (lines ~616–618).
- **Simplicity Rationale:** The repo will then contain **three** mechanical "pattern/analogy" layers: `core/upset_patterns.py` (hand-written upset DB feeding debate grounding), `core/pattern_engine.py` (pre-LLM linguistic/economic/temporal detection with historical-correlation claims, feeding the debate), and the new `incidents/` corpus. The design addresses only the first (Alternative D + a recorded fallback). It never mentions `pattern_engine.py` at all. The 3-import isolation rule makes the runtime boundary clear, but the architectural boundary is not: state explicitly that the incidents corpus does not feed pattern_engine's analogy path, and extend the "component reframe fallback" to cover it (or record why the corpus can't back it). Without that sentence, a future contributor gets two places to wire "historical analogies" and will guess. One paragraph fixes this; it is an architectural-boundary gap, not a redesign.

### 🟢 Nit — Finding 4: The problem statement mischaracterizes `core/upset_patterns.py`
- **Affected Scope:** The Problem, gap 1 (lines ~33–36).
- **Simplicity Rationale:** The claim "hand-written structural patterns with no dates, actors, or outcomes" is wrong on two of three counts: `UpsetEntry` carries `year` (date) and `actual_outcome` (outcome) for each of its ~11 cases; what it actually lacks is **actors** and — decisively — the **domain** (elections/geopolitics, not corporate exits) and **structural field matching** (it's keyword-list based). The design's real argument (neither store can answer "five closest structural analogs for a founder-CEO exit") stands, but the mischaracterization weakens the reuse analysis a reader will perform against the file. Tighten the wording to "election-domain, keyword-matched, no actor/structural fields".

### 🟢 Nit — Finding 5: "Known Risks (the three weakest points)" lists four risks
- **Affected Scope:** Lines ~576–601.
- **Simplicity Rationale:** The header is stale — the zero-agent revision added a fourth risk (research-answer quality) without updating the count. Small, but this is exactly the kind of drift a review pass exists to catch.

### 🟢 Nit — Finding 6: Token bound ignores the extraction repair retry
- **Affected Scope:** G4 (line ~88), NFR Token overhead (line ~565), CUJ 1 (line ~148) vs. extraction spec (lines ~806–811).
- **Simplicity Rationale:** "≤ ~2.3k tokens per fresh incident" is stated unconditionally, but the extraction path allows one repair retry — worst case roughly doubles the extraction call. State it as steady-state ≤ ~2.3k with a retry-bounded worst case (~2×), or CUJ 1's "Then" assertion is untestable as written.

### 🟢 Nit — Finding 7: Per-query hash-drift check is optional complexity — drop it
- **Affected Scope:** Data stores contract (line ~293), `store.py` spec (lines ~722–724).
- **Simplicity Rationale:** Server-start rebuild is sub-second at 50 records and already picks up hand edits; a per-query hash check against top-20 candidates guards a multi-writer scenario that doesn't exist in a single-user tool. The design itself marks it "optionally" — make that a cut (§ Explicit cuts) and delete the corresponding test obligation.

### 🟢 Nit — Finding 8: Verify the fastembed cache mechanism against the installed version, not a remembered env var
- **Affected Scope:** Dockerfile integration point (lines ~374–376), file 17 (lines ~766–768).
- **Simplicity Rationale:** The cold-start claim is real (current Dockerfile copies `site-packages`, `vg/`, and `chroma_db` but no model cache), but the fix names `FASTEMBED_CACHE_PATH` while `requirements.txt` pins only `fastembed>=0.1.0`; cache control in fastembed is version-dependent (constructor `cache_dir` vs env var). If the installed version ignores that env var, the fix silently fails and the Docker cold-start guarantee in the verification plan fails with it. One line: pin the fastembed version and verify the cache knob against it.

### 🟢 Nit — Finding 9: Consider a smaller seed corpus for first end-to-end validation
- **Affected Scope:** CUJ 1 given (line ~138), file 14, E2E plan (lines ~1003–1004).
- **Simplicity Rationale:** The hard gate "Nvidia demo only after the 30 curated records exist" defers all live validation behind a large hand-authoring effort, while the anti-circular-validation rationale only requires the *list* to be pre-committed, not all 30 cards authored before anything runs. The design already states small denominators honestly; validating the pipeline against a 10-record seed earlier would surface integration faults (Finding 1 included) sooner. Process simplification, not a schema change.

## Verified Claims (evidence for the reuse and accuracy audit)

| Design claim | Repo check | Result |
|---|---|---|
| `search_news()` exists as the only search dependency | `search/web.py:38` | ✅ exists (contract mismatch → Finding 1) |
| Collections use cosine space; `hybrid_retriever` converts as L2 | `rag/builder.py:85` (`hnsw:space='cosine'`) vs `rag/hybrid_retriever.py:222–223` (`1/(1+d)`, "ChromaDB uses L2") | ✅ accurate — the "bug this design does not inherit" is real |
| `do_POST` hardcoded `/api/analyze`; `X-API-Key` reusable | `api/server.py:85, 90–101` | ✅ accurate |
| RAG auto-build fires only when `chroma.sqlite3` absent | `main.py:221–230` | ✅ accurate |
| Extraction model `allam-2-7b` exists in config | `config.py:21, 62` | ✅ accurate |
| Stale `python -m veritas.rag.builder` docstring | `rag/builder.py:3` | ✅ accurate |
| `EnhancedDebateCoordinator` is the debate entry; Tavily first | `main.py:29`, `core/enhanced_debate.py:22` | ✅ accurate |
| Step 0 divergence real (`vg-main/`, `testapp/`, `cli.py`, orphan root tests) | glob + `run.py`, `api/server.py` imports | ✅ accurate and correctly sequenced first |
| G6 zero new deps | `requirements.txt:1–13` | ✅ achievable |
| Known pre-existing limiter/`asyncio.run()` note | `core/llm_client.py:64–83`, `api/server.py:116` | ✅ consistent with code |
| Docker cold-start re-download risk | `Dockerfile:29–36` (no model cache copied) | ✅ real (mechanism → Finding 8) |
| Repo ships a hash-keyed file cache (`cache.py`) | `cache.py:26–48` | ✅ exists; design's local paste-hash cache in `store.py` is consistent with its 3-import isolation rule — acceptable, no change needed |
| 350px verdict aside | not located in `style.css`/`index.html` slices inspected | ⚠️ unverified; UI-level, immaterial to the architecture |

## Verdict

**No blockers.** The zero-agent redesign is directionally right and this document is materially simpler and better-grounded than a ten-agent pipeline for a lookup problem: the root problem is addressed, the reuse decisions check out against the code, Step 0 correctly puts repo hygiene first, and the Alternatives section shows real (verifiable) rejection reasoning. Before this is build-ready, resolve the one **contract gap** (Finding 1 — the research loop has no source of structured URL+snippet data and inherits a 24-hour news filter that will hollow out the loop's historical questions) and take the two cheap altitude corrections (Finding 2 — defer the mode gate until the debate flag is ever enabled; Finding 3 — one paragraph fixing the boundary with `pattern_engine.py`). The nits are hygiene.

---

## Reviewer 2: egm-inventive-catalyst

**Mode:** REVIEW (document audit). **Target:** `docs/designs/incident-memory.md` (read in full, 1010 lines). **Grounding checks performed (read-only):** `search/web.py`, `core/llm_client.py`, `rag/hybrid_retriever.py`, `api/server.py`, `config.py`, repo root listing.

The foundational architecture (typed schema + local embeddings + mechanical scoring + parked debate) is internally coherent, and every resolution proposed below stays inside the author's fixed frame — no new dependencies, no agents, no model in the research loop, mechanical everything. The findings are unexamined compromises *within* that frame, several of them verified against the repo the design claims to integrate with unchanged.

Verified non-findings, for the merge record: `allam-2-7b` is the repo's configured `model_small` (`config.py`), so the extraction model choice is grounded; the `hybrid_retriever.py` cosine-as-L2 claim is accurate (line ~222, `1/(1+d)` labeled "L2"); Step 0's deletion targets (`cli.py`, `vg-main/`, `testapp/`, orphan root tests) all exist as described; the hardcoded `/api/analyze` comparison in `do_POST` is real.

---

**Finding 1 — 🟡 Major**
1. **Severity:** 🟡 Major
2. **Affected Scope:** Scoring and explanation mechanics; schema `outcome` field; `calibrate_weak_floor()`; Known Risk 3.
3. **False Compromise:** The outcome-sharpening term is presented as "small" (Risk 3) when it is structurally zero in the only production scoring direction. The schema fixes `outcome` as "empty for live pastes", and the scorer defines `Jaccard(∅, ·) = 0` — so the 0.05 outcome-Jaccard component contributes exactly 0.0 to every fresh-paste → corpus score (the worked example confirms: "outcome | none recorded yet | 0"). Worse, `calibrate_weak_floor()` runs leave-one-out self-matching over curated cards whose outcomes are pre-filled, so the 0.45 floor is calibrated on a scoring distribution containing a nonzero outcome component that production queries can never produce. The threshold is fitted to a regime that differs from production by exactly the component the calibration tunes.
4. **Proposed Resolution:** Mirror production during calibration — zero the outcome component in the leave-one-out pass (or exclude outcome-bearing candidates), and restate the term as dormant-until-card-has-outcome rather than a live ranking signal. If a real production path is wanted, the only one available is the rare re-score direction: a later "what happened next" paste populates the card's outcome and the same incident is re-scored.
5. **Secondary Liabilities:** Threshold semantics shift by ≤0.05 of score mass; the "sharpening" narrative weakens further (already Risk 3); any re-score path becomes a second consumer of cache invalidation (see Finding 3).

**Finding 2 — 🟡 Major**
1. **Severity:** 🟡 Major
2. **Affected Scope:** G5, CUJ 4, `store.py rebuild_index()`, Risk 1 mitigation.
3. **False Compromise:** "Curated-first matching" is load-bearing and undefined, and each possible reading betrays a stated goal. `rebuild_index()` reads *all* JSON files, and provisional records are saved to `data/incidents/*.json` behind the confirm step — so either provisional records are embedded and match (making Risk 1's "curated-first matching" mitigation void: model error propagates on the default path), or they are excluded (making the Overview's "corpus grows as a side effect of use" hollow: a pasted incident improves nothing until a separate curator promotion happens). The document invokes the term in both directions without deciding.
4. **Proposed Resolution:** Segmentation — make the participation rule explicit and visible: provisional records match with a "provisional match" label in the result and in `retrieval_debug` (or filter `status == curated` at query time and rewrite the growth promise honestly as two-step). The choice must be stated in the schema/store sections.
5. **Secondary Liabilities:** Labeled-provisional matching surfaces model error to end users (visibly — the honest version of Risk 1); filtered matching slows corpus payoff and makes the cache's corpus fingerprint more volatile (see Finding 3).

**Finding 3 — 🟡 Major**
1. **Severity:** 🟡 Major
2. **Affected Scope:** Data stores (repeat cache), `store.py`, CUJ 3, G3.
3. **False Compromise:** Cache correctness rests on an undefined `corpus_version`. The repeat-paste key is `(sha256(paste), corpus_version)`, but the document never defines how that version is computed or bumped. If it is a manually bumped constant, it never changes, and the following concrete failure occurs: record an outcome for the closest match (CUJ 3), re-paste the original incident that matched it — the cached response serves pre-outcome tiers, base rate, and timelines, so "the panel immediately renders the outcome" holds only for non-cached pastes, directly contradicting G3/CUJ 3. The design treats invalidation as a free invariant.
4. **Proposed Resolution:** `store.py` is already the sole mutation point — increment a monotonically increasing `corpus_version` integer under the same `threading.Lock` on every JSON mutation (new record, promote, prune, outcome write). Near-zero cost; makes the existing key correct by construction.
5. **Secondary Liabilities:** Every mutation invalidates all cached pastes (acceptable — mutations are rare at curator scale); a per-record hash key is possible but adds complexity for no measured benefit.

**Finding 4 — 🟡 Major**
1. **Severity:** 🟡 Major
2. **Affected Scope:** Structural mode gate (`match.py`), Alternative H rejection rationale, gap detector 1, `main.py` note.
3. **False Compromise:** The misroute cost the author used to reject Alternative H ("a misroute sends a paste to Tavily and the debate cache") reappears unhandled on the incident side of the gate. A question-shaped input pre-set to incident mode spends the full extraction call, produces a nearly-empty card, and then gap detector 1 (empty match-relevant fields) fires on almost every field — templated questions that burn up to five-to-ten Tavily searches chasing evidence for an event that never happened. The design explicitly protects debate quota from misroutes ("a misrouted paste must not burn search quota") but leaves incident quota defenseless in the mirror-image case.
4. **Proposed Resolution:** A zero-token incident-shape precondition before the loop runs: require at least one datable event plus a named actor/org in the extracted card; otherwise skip the research loop and render the empty fields as gaps (the silence line already names them). Mechanical, no tokens, no model.
5. **Secondary Liabilities:** One more mechanical rule in `gaps.py` to test; genuinely thin breaking-news stubs lose some automated research — acceptable, since they are also the no-match case.

**Finding 5 — 🟡 Major**
1. **Severity:** 🟡 Major
2. **Affected Scope:** `gaps.py` detector 4, `research.py`, scoring tiers section.
3. **False Compromise:** "Each gap emits a templated question text, a search query, and the closure target it can fill" is applied uniformly to a gap type that is structurally un-closable by search. Gap 4 (zero strong-tier matches) is a statement about corpus absence, not evidence absence — no web search can add a card to memory. Its closure target is undefined, so `research.py` either wastes one search per no-match paste on an unclosable gap or dereferences a missing target, and the mechanical stop rule must special-case a gap no search result can ever close.
4. **Proposed Resolution:** Exempt gap 4 from the one-search rule — its closure is the panel copy plus weak-tier context, already specified. Optionally invert the waste into value (Blessing in Disguise): let gap 4's single query hunt for candidate historical analogs to *suggest as future corpus records*, rendered as suggestions only — never evidence, never written back.
5. **Secondary Liabilities:** An exception to the uniform rule adds one branch in `research.py`; the suggestion variant surfaces unvetted web titles and must be labeled as suggestions, gated behind the same confirm flow.

**Finding 6 — 🟡 Major**
1. **Severity:** 🟡 Major
2. **Affected Scope:** Data flow diagram ("confirm/edit state governs SAVING only; matching runs on the in-memory card"), CUJ 1, file 26 panel flow.
3. **False Compromise:** Matches are computed from the pre-confirm card, and edits in the review state never re-score. The flow diagram runs extract → score → gaps → research → re-score → response with confirm governing *saving* only, while CUJ 1 and file 26 present the matches as belonging to "the confirmed card". Under the diagram's order, a user correcting a mis-extracted `trigger_type` or `tempo` sees tiers, base rate, and why/breaks bullets computed from the model's original fields. The design's entire provenance thesis is that model fills must not silently stand — except here, where they do, on the primary path.
4. **Proposed Resolution:** Either gate matching behind confirm (reorder: extract → confirm → match + loop; same wall-clock, reordered waiting), or re-run the free local stages on edit (re-embed + re-score cost zero tokens; re-run the loop only if match-relevant fields changed).
5. **Secondary Liabilities:** Reordering adds a second waiting period after confirm; re-scoring adds debounced UI work and audit-generation bookkeeping in the loop audit so rounds remain attributable to card generations.

**Finding 7 — 🟡 Major**
1. **Severity:** 🟡 Major
2. **Affected Scope:** Non-Functional Requirements (Rollout & Rollback), `/api/analyze` gating, files 5–6 (README, programmatic `analyze()`).
3. **False Compromise:** "Nothing existing breaks on deploy" is false under default-off. The rollout section claims additive safety "with the debate flag defaulting off so nothing existing breaks on deploy", while the same document specifies that flag-off `/api/analyze` — and `analyze()`/`analyze_async()`, which the README documents as programmatic surface — return a typed `debate_disabled` response. Existing consumers of the repo's primary feature change behavior on deploy. The default-off decision itself is not the contradiction; the safety claim contradicts the decision.
4. **Proposed Resolution:** Either default `debate_enabled: true` (preserve current behavior; the author opts out) or keep default off and restate rollout honestly: existing `/api/analyze` callers receive `debate_disabled` until the flag is set. One line either way.
5. **Secondary Liabilities:** Default-on keeps the 16.5k–66.8k-token path reachable by accident (against the cost thesis); default-off requires the explicit acknowledgment plus the UI hint (the inert Debate option already covers the UI).

**Finding 8 — 🟡 Major (verified against `search/web.py`)**
1. **Severity:** 🟡 Major
2. **Affected Scope:** Integration points ("existing code, unchanged behavior"), `research.py` (files 31, 34), search-quota accounting.
3. **False Compromise:** The research loop's "only search dependency" is claimed as reuse with unchanged behavior, but `search_news()` embeds four behaviors incompatible with mechanical research: (a) it hard-appends `" latest news"` to every query; (b) it applies a 24-hour `from_date` filter; (c) it returns a display-formatted string (📰 header, a Tavily AI-generated "SUMMARY:" line, `[i] title / 220-char content / Source: url` lines); (d) it silently re-searches on exception — a second Tavily call. Consequences by construction: historical/expected-evidence questions (filings, board statements, market reactions older than a day) return zero results, so such gaps close as "no source available" — not because sources don't exist but because the filter hides them; "claim text from the snippet" requires a fragile parser over a display string whose AI-answer line is not a source at all; and the fallback path can double the per-question search count, breaking the exact "one search per question" arithmetic the specified tests assert.
4. **Proposed Resolution:** Give `search_news()` an optional `from_date: Optional[str] = None` parameter whose default preserves debate behavior exactly; have `research.py` pass a wide window. Add a strict parser contract (or structured-return variant) for `(title, snippet, url)` triples that explicitly excludes the SUMMARY line. Count the fallback re-search in the per-query dedupe ledger so quota tests stay truthful.
5. **Secondary Liabilities:** Touching shared search code risks debate-path regressions (mitigated by the default-preserving parameter); wider date windows return noisier snippets, which the `reported_unconfirmed` ceiling already contains; the parser contract is one more invariant to test.

**Finding 9 — 🟢 Nit**
1. **Severity:** 🟢 Nit
2. **Affected Scope:** Mode gate override handling (Alternative H resolution, file 26).
3. **False Compromise:** "One-click override with logging" names no destination — the loop audit rides in the response, but the override log's home (response field? server log?) is unspecified, making the promise unverifiable as written.
4. **Proposed Resolution:** Name it — e.g., an override field in the incident-match response plus one server log line.
5. **Secondary Liabilities:** None beyond one response field.

**Finding 10 — 🟢 Nit**
1. **Severity:** 🟢 Nit
2. **Affected Scope:** Non-Functional Requirements (Performance & Latency); extraction call spec.
3. **False Compromise:** Worst-case latency is understated: a 45–60s extraction timeout plus up to ten searches at 1–2s each puts the true ceiling near ~80s+, while the NFR says "on the order of tens of seconds". Note also the 45–60s timeout is deliberately far above the repo's default `groq_request_timeout_seconds: 18` — a new operational posture presented as routine.
4. **Proposed Resolution:** Restate the worst case honestly (or trim the cap), and state explicitly that the extraction timeout intentionally exceeds the repo default.
5. **Secondary Liabilities:** Copy honesty only; UI spinner expectations adjust accordingly.

---

**Summary for the merge:** The zero-agent redesign resolves its headline contradictions honestly (cost vs memory, grounding vs flexibility); no Blocker-level false compromise was found. The residual compromises cluster in one theme: mechanisms the design borrows or promises for free — search reuse "unchanged", cache correctness, calibration regime, confirm-state semantics, "curated-first" — each carry a hidden dependency the document treats as an invariant rather than a decision. All ten findings resolve mechanically or as copy edits inside the fixed frame.
