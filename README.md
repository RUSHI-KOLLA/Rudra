# VG — Mini CID Investigator

**One question in. Six investigative lenses out. Every finding carries its source.**

A lean, free-tier-deployable investigation service. You ask a question about a
person, company or event; the investigator fans it out across six lenses, pulls
real findings from keyless public sources, tags the provenance of each claim,
flags contradictions between lenses, and returns a briefing.

There is no debate mode, no persona simulation and no vector database. The
product is one endpoint and one job: find what is actually knowable about a
question and show the evidence.

---

## The six lenses

| Lens | Question it asks | Typical sources |
|---|---|---|
| **Money** | Who paid, who benefited, who lost? | Google News, SEC EDGAR filings |
| **Power** | Who appointed, who could remove, who protected? | Google News, Wikidata |
| **Secrecy** | What is reported but unconfirmed? Who won't comment? | Google News, GDELT |
| **Timing** | What changed in the weeks before? | Dated news results |
| **Network** | Who else is connected to these people or firms? | Wikidata, GLEIF, OpenSanctions |
| **Counter-case** | What would have to be true for the official story to be whole? | Adversarial queries |

Lenses are *perspectives*, not personas. They do not generate opinions — they
run different questions against different sources.

---

## Quick start

```bash
pip install -r requirements.txt

# Start the server
PYTHONPATH=. python -m vg.main --web --port 8080
# or: python run.py
```

```bash
curl -X POST http://127.0.0.1:8080/api/incident-investigate \
  -H "Content-Type: application/json" \
  -d '{"question":"Why did Chanda Kochhar resign from ICICI Bank in 2018?"}'
```

No key is needed: every source is keyless and the synthesis falls back to a
deterministic mechanical summary. Add your own Groq key to get the LLM
briefing instead:

```bash
curl -X POST http://127.0.0.1:8080/api/incident-investigate \
  -H "X-API-Key: gsk_your_key" \
  -H "Content-Type: application/json" \
  -d '{"question":"Why did Chanda Kochhar resign from ICICI Bank in 2018?"}'
```

Open `http://127.0.0.1:8080/` in a browser for the investigator UI.

---

## API

### `POST /api/incident-investigate`

**Request**

```json
{ "question": "Why did Chanda Kochhar resign from ICICI Bank in 2018?" }
```

**Response**

```jsonc
{
  "question": "...",
  "question_profile": {            // mechanical extraction, computed once
    "entities": ["Chanda Kochhar", "ICICI Bank"],
    "dates": ["2018"],
    "amounts": []
  },
  "lens_results": {
    "money": {
      "queries": ["\"Chanda Kochhar\" payment contract funding"],
      "findings": [
        {
          "title": "...",
          "url": "https://...",
          "snippet": "...",
          "date": "2018-06-18",
          "tag": "reported_unconfirmed",
          "lens": "money",
          "question": "...",         // the query that surfaced it
          "corroboration": 3         // how many distinct lenses surfaced this URL
        }
      ]
    }
    // power, secrecy, timing, network, counter_case
  },
  "contradictions": [
    {
      "lens_a": "money",
      "lens_b": "secrecy",
      "subject": "Kochhar",
      "finding_a": "...",
      "finding_b": "...",
      "type": "denial_vs_affirmation"
    }
  ],
  "provenance": {
    "total_findings": 132,          // distinct sources (a URL counts once)
    "unique_sources": 132,
    "lens_findings": 185,           // the same sources seen across lenses
    "tag_counts": { "reported_unconfirmed": 107, "inferred": 25 },
    "lenses_run": ["money", "power", "secrecy", "timing", "network", "counter_case"]
  },
  "synthesis": "Investigation of: ..."   // LLM briefing or mechanical summary
}
```

**Status codes**

| Code | Meaning |
|---|---|
| `200` | Investigation completed |
| `400` | `question` missing, empty, over-long, or a malformed body |
| `401` | Deployment access key missing or wrong (only when one is configured) |
| `413` | Request body over the size limit |
| `429` | Rate limit exceeded |
| `500` | Investigation failed (detail in the body) |

### Access and keys — two different things

| Header | What it is | Effect |
|---|---|---|
| `X-API-Key` | The **caller's own** Groq key (BYOK) | Enables the one LLM synthesis call. Never stored. Not authentication. |
| `X-VG-Access-Key` | The **deployment** secret (`VG_ACCESS_KEY`) | Required on every request when configured. Only then may the server spend its own `GROQ_API_KEY`. |

The endpoint is **open by default** and rate-limited per client address
(10 investigations/minute). In open mode the server's Groq quota is *never*
spent on a caller's behalf — an anonymous request gets the mechanical summary.
Set `VG_ACCESS_KEY` to lock the endpoint down: requests without the key get
`401`, and authorized requests may use the server's `GROQ_API_KEY` for the
synthesis call.

Cross-origin browser calls are refused unless the origin is listed in
`VG_ALLOWED_ORIGINS`; the bundled UI is same-origin and needs nothing.

### `GET /api/health`

```json
{ "status": "ok", "service": "vg-web", "version": "2.0", "mode": "saas",
  "modes": ["investigate"], "auth": "open" }
```

`auth` is `open` or `access_key`, so a client can tell whether it needs the
deployment key.

---

## How it works

```
question
   │
   ├─ extract subjects / dates / amounts  →  question_profile
   │
   ├─ six lenses × subject  (all concurrent)
   │     └─ free search + structured sources  →  findings (title, url, snippet, date)
   │
   ├─ corroboration: how many distinct lenses surfaced each URL
   ├─ contradictions: opposing claims about a shared subject, across lenses
   ├─ provenance: tag counts + unique source count
   └─ synthesis: one bounded Groq call (optional) → mechanical fallback
```

**Subjects** — the investigator reads the question the way a person would:
full names (`Chanda Kochhar`), a surname alone (`Kochhar`), an acronym
(`RBI`), a one-word company (`Boeing`), a name carrying an organisation
suffix (`State Bank`, `ICICI Bank`) and `of` style names (`Bank of Baroda`).
A question that names nobody (`Why did the CEO resign?`) falls back to its
content words so the lenses still have something to search.

**Provenance tags** — every finding carries one:

| Tag | Meaning |
|---|---|
| `documented` | Verified against a primary source artifact |
| `reported_unconfirmed` | Reported by a source, not independently verified |
| `inferred` | Derived from structured data (Wikidata, EDGAR, GLEIF) |
| `speculative` | Low-confidence / weakest tier |

**Corroboration** — the same URL surfacing in several lenses is a strength
signal, not a duplicate. `corroboration: 4` means four *distinct* lenses
independently pointed at that source; the same article twice in one lens
counts once.

**Contradictions** — opposite-polarity claims (`denied` vs `confirmed`) about
the *same* subject, found in *different* lenses. Two lenses agreeing is never
a contradiction, two parallel legal developments (a sanction quashed vs an
asset attachment upheld) are not flagged as opposing either, and mutually
exclusive outcomes (acquittal vs conviction) are. Uncertainty is not
negation: "unconfirmed" does not contradict "confirmed".

---

## Performance

The six lenses, their subjects and their queries all run concurrently, so a
slow source delays only its own work:

| Measurement | Value |
|---|---|
| Wall time, one investigation (~180 findings across 6 lenses) | ~12 s |
| Response size | ~150 KB |
| Peak RSS during an investigation | ~35 MB |
| Requests to Wikidata for one entity | 1 batched (was up to 150) |
| Container image | 223 MB |
| Docker build context | 6 MB |

Every request is bounded: body ≤ 64 KiB, question ≤ 500 characters, ≤ 40
findings per lens, ≤ 60 s of investigation time, and a per-client rate limit.

---

## Sources — all free, no paid APIs

| Source | Key needed? | Notes |
|---|---|---|
| Google News RSS | No | Primary news source; headlines + publisher |
| GDELT | No | Throttled fallback (1 req / 5 s), `ENABLE_GDELT=0` to disable |
| SEC EDGAR | No | Structured filings for the money lens |
| Wikidata | No | Structured entity/relationship data |
| GLEIF | No | Legal entity registry lookup |
| OpenSanctions | Optional | Deep sanctions/PEP coverage with a key |
| Brave Search | Optional | Requires a credit card at signup — not needed |
| DuckDuckGo | Optional | `ENABLE_DDGS=1`; off by default (rate limits) |

Without a single API key the investigator still works.

---

## Configuration

All variables are optional.

```bash
# LLM synthesis (one bounded call per investigation).
# Without it the investigator returns its deterministic mechanical summary.
# The server's key is only used for requests that carry VG_ACCESS_KEY.
GROQ_API_KEY=
GROQ_MODEL_LARGE=openai/gpt-oss-120b
VG_TEMPERATURE=0.2
VG_MAX_TOKENS=1500

# Deployment access key. Set it to lock the endpoint down: requests must
# present it in X-VG-Access-Key, and only then is GROQ_API_KEY used.
VG_ACCESS_KEY=

# Request budgets
VG_RATE_LIMIT_PER_MINUTE=10
VG_MAX_QUESTION_CHARS=500
VG_MAX_BODY_BYTES=65536
VG_MAX_INVESTIGATION_SECONDS=60

# Cross-origin access (the bundled UI is same-origin and needs nothing)
VG_ALLOWED_ORIGINS=

# Server binding
PORT=8080
VG_HOST=0.0.0.0

# Optional sources
BRAVE_API_KEY=
OPENSANCTIONS_API_KEY=
ENABLE_GDELT=1
ENABLE_DDGS=0
```

See `.env.example`.

---

## Tests

```bash
python3 -m pytest -q
```

The suite never touches the network — every source call is gated behind a test
flag.

---

## Deploy (free tier)

**Docker** (used by Koyeb, Hugging Face Spaces, Fly, Railway):

```bash
docker build -t vg-cid .
docker run -p 8080:7860 vg-cid
```

The image is ~223 MB: `python:3.11-slim` plus `requests`, `python-dotenv` and
the optional `groq` SDK. No embedding model, no vector database, no browser
downloads at build time.

**Render / any Python host** — `Procfile` and `render.yaml` are included:

```
web: PYTHONPATH=. python -m vg.main --web --port $PORT
```

---

## Repo layout

```
vg/
  api/
    server.py            HTTP server: routes, auth, JSON contracts
    static/index.html    investigator UI (no build step)
  incidents/
    investigation.py     pipeline: lenses → corroboration → contradictions → synthesis
    sources.py           free search + structured sources
  config.py              environment configuration
  main.py                entry point (web server only)
tests/                   offline test suite
Dockerfile               two-stage, minimal runtime image
```

## License

See repository metadata.
