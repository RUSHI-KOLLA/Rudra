# VG — Mini CID Investigator · Quick Start

One question in. Six investigative lenses out. Every finding carries its source.

## Run it locally

```bash
pip install -r requirements.txt
PYTHONPATH=. python -m vg.main --web --port 8080
```

Then open <http://127.0.0.1:8080/> — paste your Groq key in the setup overlay
if you want the AI briefing (it is kept in your browser tab only and used for
one synthesis call), or click **SKIP** and use the mechanical summary.

## Run it without a key

The investigation itself needs no API key at all. Google News RSS, GDELT,
Wikidata, SEC EDGAR and GLEIF are all keyless.

```bash
curl -X POST http://127.0.0.1:8080/api/incident-investigate \
  -H "Content-Type: application/json" \
  -d '{"question":"Why did Chanda Kochhar resign from ICICI Bank in 2018?"}'
```

Add your own Groq key for the LLM briefing:

```bash
curl -X POST http://127.0.0.1:8080/api/incident-investigate \
  -H "X-API-Key: gsk_your_key" \
  -H "Content-Type: application/json" \
  -d '{"question":"Why did Chanda Kochhar resign from ICICI Bank in 2018?"}'
```

## Locking it down

Set `VG_ACCESS_KEY` to require a deployment key on every request (sent as
`X-VG-Access-Key`). Only then may the server spend its own `GROQ_API_KEY`.
Without it the endpoint is open and rate-limited (10 requests/minute per
client).

```bash
VG_ACCESS_KEY=choose-a-secret PYTHONPATH=. python -m vg.main --web --port 8080
```

## Try it from Python

```python
from vg.incidents import investigate

result = investigate("Why did Chanda Kochhar resign from ICICI Bank in 2018?")
print(result["provenance"])      # findings, unique sources, tag counts
print(result["lens_results"])    # money / power / secrecy / timing / network / counter_case
print(result["contradictions"])  # opposing claims across lenses
print(result["synthesis"])       # briefing
```

`investigate()` uses only the key you pass it — it never reads `GROQ_API_KEY`
from the environment, so a server can decide who is allowed to spend its
quota:

```python
result = investigate(question, api_key=os.getenv("GROQ_API_KEY"))
```

## Tests

```bash
python3 -m pytest -q
```

The suite never touches the network.

## Deploy

Docker (Koyeb / HF Spaces / Fly / Railway):

```bash
docker build -t vg-cid .
docker run -p 8080:7860 vg-cid
```

Any Python host — `Procfile` and `render.yaml` are included:

```
web: PYTHONPATH=. python -m vg.main --web --port $PORT
```

See `README.md` for the full API contract, the six lenses and the source list.
