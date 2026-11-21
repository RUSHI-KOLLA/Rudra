# VG — Mini CID Investigator · Quick Start

One question in. Six investigative lenses out. Every finding carries its source.

## Run it locally

```bash
pip install -r requirements.txt
PYTHONPATH=. python -m vg.main --web --port 8080
```

Then open <http://127.0.0.1:8080/> — paste your Groq key in the setup overlay
(it is stored only in your browser's localStorage and used for one synthesis
call), or use the API directly.

## Run it without a key

The investigation itself needs no API key at all. Google News RSS, GDELT,
Wikidata, SEC EDGAR and GLEIF are all keyless. Without a Groq key the
synthesis falls back to a deterministic mechanical summary.

```bash
curl -X POST http://127.0.0.1:8080/api/incident-investigate \
  -H "X-API-Key: anything" \
  -H "Content-Type: application/json" \
  -d '{"question":"Why did Chanda Kochhar resign from ICICI Bank in 2018?"}'
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
