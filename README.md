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
  -H "X-API-Key: your-key" \
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
    "entities": ["Chanda Kochhar"],
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
          "corroboration": 3         // how many lenses surfaced this URL
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
    "total_findings": 148,
    "unique_sources": 109,
    "tag_counts": { "reported_unconfirmed": 115, "inferred": 33 },
    "lenses_run": ["money", "power", "secrecy", "timing", "network", "counter_case"]
  },
  "synthesis": "Investigation of: ..."   // LLM briefing or mechanical summary
}
```

**Status codes**

| Code | Meaning |
|---|---|
| `200` | Investigation completed |
| `400` | `question` missing or empty |
| `401` | No `X-API-Key` header (and no server-side key) |
| `500` | Investigation failed (detail in the body) |

### `GET /api/health`

```json
{ "status": "ok", "service": "vg-web", "version": "2.0", "mode": "saas",
  "modes": ["investigate"] }
```

---

## How it works

```
question
   │
   ├─ extract entities / dates / amounts  →  question_profile
   │
   ├─ six lenses × entity
   │     └─ free search + structured sources  →  findings (title, url, snippet, date)
   │
   ├─ corroboration: count how many lenses surfaced each URL
   ├─ contradictions: opposing claims about a shared subject, across lenses
   ├─ provenance: tag counts + unique source count
   └─ synthesis: one bounded Groq call (optional) → mechanical fallback
```

**Provenance tags** — every finding carries one:

| Tag | Meaning |
|---|---|
| `documented` | Verified against a primary source artifact |
| `reported_unconfirmed` | Reported by a source, not independently verified |
| `inferred` | Derived from structured data (Wikidata, EDGAR, GLEIF) |
| `speculative` | Low-confidence / weakest tier |

**Corroboration** — the same URL surfacing in several lenses is a strength
signal, not a duplicate. `corroboration: 4` means four lenses independently
pointed at that source.

**Contradictions** — opposite-polarity claims (`denied` vs `confirmed`) about
the *same* subject, found in *different* lenses. Two lenses agreeing is never
a contradiction, and two parallel legal developments (a sanction quashed vs an
asset attachment upheld) are not flagged as opposing either.

---

## Performance

The six lenses run concurrently, so a slow source delays only its own lens:

| Measurement | Value |
|---|---|
| Wall time, one investigation (~146 findings, 6 lenses) | ~15 s |
| Peak RSS during an investigation | ~35 MB |
| Requests to Wikidata for one entity | 1 batched (was up to 150) |
| Container image | 223 MB |
| Docker build context | 6 MB |

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
GROQ_API_KEY=
GROQ_MODEL_LARGE=openai/gpt-oss-120b
VG_TEMPERATURE=0.2
VG_MAX_TOKENS=1500

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
