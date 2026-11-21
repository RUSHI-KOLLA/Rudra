# CID-Only Cleanup & Accuracy Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the product to a single, accurate "mini CID investigator" — one question in, six investigative lenses, real sourced findings out — and delete the debate/RAG/match subsystems that make it heavy and dilute it.

**Architecture:** `POST /api/incident-investigate` is the only endpoint. `incidents/sources.py` fans a question out across six lenses (Google News RSS → GDELT → Brave, plus Wikidata/EDGAR/GLEIF/OpenSanctions), `incidents/investigation.py` runs the lenses, tags provenance, computes cross-lens corroboration, detects contradictions, and synthesises (optional bounded LLM call, mechanical fallback). Everything else in the repo is deleted.

**Tech Stack:** Python 3.11, stdlib `http.server`, `requests`, optional `groq` for synthesis, ChromaDB/fastembed/onnxruntime **removed**.

**Spec:** This plan (the cleanup design was agreed in conversation: delete debate mode, persona RAG, and the old paste-an-incident match flow; keep and strengthen only the investigator).

## Global Constraints

- The only API endpoint is `POST /api/incident-investigate`. `GET /api/health` stays. Static file serving stays.
- HTTP contracts preserved: `401` missing key, `400` missing question, `200` with `{question, lens_results, synthesis, provenance, contradictions}`.
- No network calls in the test suite (`_IN_TEST` gate in `incidents/sources.py` stays).
- No paid APIs. Optional keys only: `BRAVE_API_KEY`, `OPENSANCTIONS_API_KEY`, `GROQ_API_KEY` (synthesis only).
- Free-tier deployable: no `chromadb`, `fastembed`, `onnxruntime`, `numpy`, `tavily-python` in `requirements.txt`.
- Every provenance tag stays in `{documented, reported_unconfirmed, inferred, speculative}`.
- Python 3.11 syntax (the Docker base image); `from __future__ import annotations` used where `X | None` appears.

## Review Focus

- A question naming one entity must not produce duplicate evidence across lenses — the same URL must count once in totals but show how many lenses surfaced it.
- A question with no date must not emit date findings; a question with a year must emit the full year (`2018`), never a fragment (`20`).
- Contradiction detection must fire on opposing claims from *different* lenses about the same subject, and must not fire on two lenses saying the same thing.
- With no `GROQ_API_KEY` set, `investigate()` must still return a non-empty `synthesis` string and must not make any network call.
- With `GROQ_API_KEY` set but the API unreachable, synthesis must fall back to the mechanical summary instead of raising.
- `POST /api/incident-investigate` must return `401` when no key is supplied, `400` for a missing question, and `200` with six lenses otherwise.

---

### Task 1: Fix year extraction (accuracy bug)

**Files:**
- Modify: `incidents/sources.py` (`_YEAR_RE`)
- Test: `tests/test_incident_investigation.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `extract_dates(text) -> list[str]` now returns full years.

- [ ] **Step 1: Write the failing test**

```python
def test_extract_dates_returns_full_years(self):
    from vg.incidents.sources import extract_dates
    dates = extract_dates("The event happened in 2018 and 2019 and 2020.")
    assert "2018" in dates and "2019" in dates and "2020" in dates
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python3 -m pytest tests/test_incident_investigation.py -k full_years -q`
Expected: FAIL — current output is `['20']` (the regex captures only the `(19|20)` group).

- [ ] **Step 3: Fix the regex**

Change `_YEAR_RE` to `re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")` — non-capturing group so `findall` returns the whole year.

- [ ] **Step 4: Run the test and verify it passes**

Run: `python3 -m pytest tests/test_incident_investigation.py -q` → Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add incidents/sources.py tests/test_incident_investigation.py
git commit -m "fix: extract full years instead of the century prefix"
```

---

### Task 2: Cross-lens corroboration + drop mechanical padding

**Files:**
- Modify: `incidents/investigation.py`
- Test: `tests/test_incident_investigation.py`

**Interfaces:**
- Consumes: `search_*` lens functions from `incidents/sources.py` (unchanged).
- Produces: `investigate(question) -> dict` gains key `question_profile` (`{"entities": [...], "dates": [...], "amounts": [...]}`); every lens finding gains key `corroboration` (int, number of lenses that surfaced it).

- [ ] **Step 1: Write the failing tests**

```python
def test_question_profile_holds_mechanical_extractions(self):
    result = inv_mod.investigate("Why did Chanda Kochhar resign in 2018?")
    profile = result["question_profile"]
    assert profile["dates"] and "2018" in profile["dates"]
    assert profile["entities"]

def test_mechanical_findings_are_not_repeated_per_lens(self):
    result = inv_mod.investigate("Why did Chanda Kochhar resign in 2018?")
    for lens, data in result["lens_results"].items():
        titles = [f["title"] for f in data["findings"]]
        assert not any(t.startswith("Entity:") or t.startswith("Date:") or t.startswith("Amount:") for t in titles)

def test_finding_corroboration_counts_lenses(self, monkeypatch):
    # same URL returned by two different lenses
    ...
    assert max(f["corroboration"] for f in money_findings) == 2
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python3 -m pytest tests/test_incident_investigation.py -k "question_profile or corroboration or mechanical_findings" -q`
Expected: FAIL — no `question_profile` key, no `corroboration` key.

- [ ] **Step 3: Implement**

In `investigation.py`:
- Remove the per-lens Entity/Date/Amount finding loops from `_run_lens`.
- Build `question_profile` once in `investigate()` from `_extract_entities` and `_extract_dates_amounts`.
- After all lenses run, count findings by URL across lenses and set `corroboration` on each finding (1 when unique).

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python3 -m pytest tests/test_incident_investigation.py -q` → Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add incidents/investigation.py tests/test_incident_investigation.py
git commit -m "feat: cross-lens corroboration and single question profile"
```

---

### Task 3: Stronger contradiction detection

**Files:**
- Modify: `incidents/investigation.py` (`_detect_contradictions`)
- Test: `tests/test_incident_investigation.py`

**Interfaces:**
- Consumes: `lens_results` dict (unchanged shape).
- Produces: `_detect_contradictions(lens_results) -> list[dict]`; each contradiction gains key `subject` (the entity token both findings share) and keeps `lens_a`, `lens_b`, `finding_a`, `finding_b`, `type`.

- [ ] **Step 1: Write the failing test**

```python
def test_detects_opposing_claims_about_same_subject(self, monkeypatch):
    # money lens: "ICICI Bank confirmed the payment was approved"
    # secrecy lens: "ICICI Bank denied approving the payment"
    # -> exactly one contradiction with type "opposing_claims"
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python3 -m pytest tests/test_incident_investigation.py -k opposing_claims -q`
Expected: FAIL — current detector only knows denial vs affirmation keywords and never reports a subject.

- [ ] **Step 3: Implement**

- Replace the keyword pair with two opposing concept sets: `NEGATION = {"denied", "denies", "deny", "quashed", "rejected", "reversed", "cleared", "dismissed", "refuted", "false", "baseless", "unsubstantiated"}` and `AFFIRMATION = {"confirmed", "admits", "admitted", "acknowledged", "upheld", "approved", "revealed", "established", "convicted", "indicted"}`.
- Require the two findings to share a subject token (capitalised word from the title/snippet, length ≥ 4) before recording a contradiction.
- Keep `type` as `"denial_vs_affirmation"` for backward compatibility with existing assertions; add `subject`.

- [ ] **Step 4: Run the test and verify they pass**

Run: `python3 -m pytest tests/test_incident_investigation.py -q` → Expected: all pass (including the existing `test_contradiction_detection_no_false_positives`).

- [ ] **Step 5: Commit**

```bash
git add incidents/investigation.py tests/test_incident_investigation.py
git commit -m "feat: subject-aware contradiction detection"
```

---

### Task 4: Optional bounded LLM synthesis with mechanical fallback

**Files:**
- Modify: `incidents/investigation.py`
- Test: `tests/test_incident_investigation.py`

**Interfaces:**
- Consumes: `GROQ_API_KEY` env var.
- Produces: `investigate()` `synthesis` field is a non-empty string in all cases. `_synthesize(question, lens_results, contradictions) -> str` calls Groq only when a key is present and not in test mode; on any failure it returns the mechanical summary.

- [ ] **Step 1: Write the failing tests**

```python
def test_synthesis_without_key_is_mechanical(self, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    result = inv_mod.investigate("Why did the CEO resign?")
    assert result["synthesis"].startswith("Investigation of:")

def test_synthesis_uses_llm_when_key_present(self, monkeypatch):
    # monkeypatch the groq client to return "LLM SUMMARY"
    # assert result["synthesis"] == "LLM SUMMARY"

def test_synthesis_falls_back_when_llm_fails(self, monkeypatch):
    # monkeypatch the groq client to raise
    # assert result["synthesis"].startswith("Investigation of:")
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python3 -m pytest tests/test_incident_investigation.py -k synthesis -q`
Expected: FAIL — no LLM path exists.

- [ ] **Step 3: Implement**

- Add `_groq_synthesis(question, lens_results, contradictions) -> str | None` that lazily imports `groq`, builds a compact prompt (question, per-lens top 5 titles + tags, contradictions), and requests `max_tokens=SYNTHESIS_MAX_TOKENS`.
- `_synthesize` calls it only when `os.getenv("GROQ_API_KEY")` is set and `_IN_TEST` is False; on exception or empty response, falls back to the existing mechanical summary.
- Keep the mechanical summary exactly as it is today (it is the no-key path).

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python3 -m pytest tests/test_incident_investigation.py -q` → Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add incidents/investigation.py tests/test_incident_investigation.py
git commit -m "feat: optional bounded LLM synthesis with mechanical fallback"
```

---

### Task 5: Strip debate / match from the server, main, config, deps, image

**Files:**
- Modify: `api/server.py`, `main.py`, `config.py`, `requirements.txt`, `Dockerfile`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `investigate(question)` from `incidents/investigation.py`.
- Produces: dispatch table contains only `/api/incident-investigate` (plus `/api/health` and static); `GET /api/health` reports `"debate_enabled": false` replaced by `"modes": ["investigate"]`.

- [ ] **Step 1: Write the failing test**

```python
def test_analyze_endpoint_is_gone(self):
    # POST /api/analyze -> 404
def test_incident_match_endpoint_is_gone(self):
    # POST /api/incident-match -> 404
def test_health_lists_only_investigate(self):
    # GET /api/health -> body["modes"] == ["investigate"]
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python3 -m pytest tests/test_api.py -q`
Expected: FAIL — `/api/analyze` currently answers 409 and `/api/incident-match` answers 200/401.

- [ ] **Step 3: Implement**

`api/server.py`:
- Remove `from vg.main import analyze_async`, the `vg.incidents.match` import block, and `from vg.incidents.store import IncidentStoreError`.
- Remove `_handle_analyze`, `_handle_incident_match`, `_send_match_error`, and the `ExtractionIncomplete` / `IncidentStoreError` branches.
- Dispatch table: `"/api/incident-investigate"` only.
- `/api/health`: report `"modes": ["investigate"]`.

`main.py`:
- Delete `analyze_async`, `analyze`, `print_report`, `byok_setup`, `run_cli`, and the `ForecastDisabledError` class.
- `run_web` no longer builds ChromaDB or the incident index.
- `__main__` only starts the web server.

`config.py`:
- Remove `chroma_db_path`, `rag_top_k`, `rag_chunk_words`, `debate_enabled`, `incidents_research_enabled`, `disable_web_search`, `tavily_api_key` and their env wiring. Keep the Groq key, model names, and any fields still referenced by the surviving code.

`requirements.txt`: remove `chromadb`, `fastembed`, `tavily-python`. Keep `requests`, `groq`, `python-dotenv`, `tenacity` only if still imported.

`Dockerfile`: remove the `python -m vg.rag.builder` pre-bake step and the `COPY --from=builder /app/chroma_db ./chroma_db` line.

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python3 -m pytest tests/test_api.py -q` → Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add api/server.py main.py config.py requirements.txt Dockerfile tests/test_api.py
git commit -m "refactor: serve only the incident investigator endpoint"
```

---

### Task 6: Delete the dead subsystems and their tests

**Files:**
- Delete: `agents/`, `core/`, `rag/`, `search/`, `cache.py`, `setup.py`, `politicore/`, `open-claude-code/`, `data/`, `incidents/match.py`, `incidents/store.py`, `incidents/scoring.py`, `incidents/gaps.py`, `incidents/research.py`, `incidents/search/`, `incidents/schema.py`, `vg/` symlink targets that no longer exist
- Modify: `incidents/__init__.py`, `vg/` symlink dir, `.dockerignore`
- Delete tests: `tests/test_debate.py`, `tests/test_implementations.py`, `tests/test_incident_research.py`, `tests/test_incident_scoring.py`, `tests/test_incident_phase3.py`, `tests/test_web.py`, `tests/live_scoring_test.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `vg.incidents` package exposing only `investigate` and the source helpers; `vg` package containing only `config.py`, `main.py`, `incidents/`, `api/`.

- [ ] **Step 1: Write the failing test**

```python
def test_incidents_package_has_no_store_dependency(self):
    import vg.incidents as pkg
    assert not hasattr(pkg, "rebuild_index")
    assert not hasattr(pkg, "load_all_cards")
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python3 -m pytest tests/test_incident_investigation.py -k no_store_dependency -q`
Expected: FAIL — `vg.incidents` currently exports `rebuild_index` / `load_all_cards`.

- [ ] **Step 3: Implement**

- Delete the listed directories and files (`rm -rf`), plus the now-dangling `vg/agents`, `vg/core`, `vg/rag`, `vg/search`, `vg/politicore` symlinks.
- Rewrite `incidents/__init__.py` to export only `investigate` and the `sources` helpers, with a docstring stating the package's single responsibility.
- Remove `incidents/schema.py` and the unused `from .schema import ...` / `from .scoring import ...` lines in `incidents/investigation.py` (verify with grep that `IncidentCard`, `Tag`, `apply_tag_cascade`, `score`, `WEIGHTS_VERSION`, `tier_label` are unreferenced).
- Remove `data/` (the 50-card incident corpus belonged to the match flow).
- `.dockerignore`: keep the media exclusions.

- [ ] **Step 4: Run the full suite and verify it passes**

Run: `python3 -m pytest -q` → Expected: all remaining tests pass (investigation + api only).

- [ ] **Step 5: Verify no dangling imports**

Run: `python3 -c "import vg.main, vg.api.server, vg.incidents"` → Expected: no output, exit 0.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: delete debate, RAG and incident-match subsystems"
```

---

### Task 7: UI becomes INVESTIGATE-only

**Files:**
- Modify: `api/static/index.html`
- Test: manual + `tests/test_api.py` static smoke check

**Interfaces:**
- Consumes: `POST /api/incident-investigate` with `{question}`.
- Produces: single-mode UI; no `INCIDENT` button, no dynamic `DEBATE` button, no call to `/api/incident-match` or `/api/analyze`.

- [ ] **Step 1: Write the failing test**

```python
def test_static_ui_has_no_debate_or_match_calls(self):
    html = Path("api/static/index.html").read_text()
    assert "/api/analyze" not in html
    assert "/api/incident-match" not in html
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python3 -m pytest tests/test_api.py -k no_debate_or_match -q`
Expected: FAIL — both endpoint strings are present.

- [ ] **Step 3: Implement**

- Delete the `INCIDENT` mode button and its mode branch; keep the `INVESTIGATE` button as the active default.
- Delete the JS block that appends a `DEBATE` button when `debate_enabled` is true.
- Delete the incident-match submit handler and its result rendering; keep the investigate submit handler and rendering.
- Keep the health/status line, but display "Investigator" instead of "Debate mode: disabled".

- [ ] **Step 4: Run the test and verify it passes**

Run: `python3 -m pytest tests/test_api.py -q` → Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add api/static/index.html tests/test_api.py
git commit -m "refactor: investigate-only web UI"
```

---

### Task 8: End-to-end verification

**Files:**
- Modify: `README.md` (or create it) — one-paragraph description of the single endpoint and the env vars.

**Interfaces:**
- Consumes: everything above.
- Produces: verified evidence that the CID investigator works end to end.

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m pytest -q` → Expected: all pass, no network access.

- [ ] **Step 2: Start the server and check the HTTP contracts**

Run: `python3 -c "from api.server import run_server; run_server('127.0.0.1', 8013)"` (background), then:
- `POST /api/incident-investigate` without a key → `401`
- with a key and no question → `400`
- with a key and a question → `200`, six lenses, findings with URLs.

- [ ] **Step 3: Check the live response content**

Assert the 200 response contains `reported_unconfirmed` findings, `question_profile`, and `corroboration` values ≥ 1.

- [ ] **Step 4: Confirm the dependency surface**

Run: `pip list 2>/dev/null | grep -Ei "chromadb|fastembed|onnxruntime"` → Expected: the project no longer requires them (they may still be installed in this dev environment; the proof is `requirements.txt`).
Run: `cat requirements.txt` → Expected: no `chromadb`, no `fastembed`, no `tavily-python`.

- [ ] **Step 5: Measure the build context**

Run: `tar -cf - --exclude-vcs --exclude-from=.dockerignore . | wc -c` → Expected: well under 10 MB.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "docs: describe the single-endpoint CID investigator"
```
