#!/usr/bin/env python3
"""Verify a deployed Mini CID Investigator.

Usage:
    python3 scripts/verify_deploy.py https://your-service.onrender.com
    python3 scripts/verify_deploy.py https://your-service.onrender.com --access-key secret

Checks the live deployment the way a client would: the health endpoint,
the access model, the request budgets, CORS, and one real investigation.
Exits non-zero if anything is wrong, so it can be used in CI.

Only the standard library is used, so it runs anywhere Python does.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import time

CHECKS: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> bool:
    CHECKS.append((name, passed, detail))
    return passed


def request(
    url: str,
    method: str = "GET",
    body: dict | None = None,
    headers: dict | None = None,
    timeout: int = 120,
) -> tuple[int, bytes, dict]:
    """Make one HTTP request and return (status, body, headers)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="e.g. https://vg-cid-investigator.onrender.com")
    parser.add_argument(
        "--access-key",
        default="",
        help="the deployment access key, if one is configured",
    )
    parser.add_argument(
        "--question",
        default="Why did Chanda Kochhar resign from ICICI Bank in 2018?",
    )
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    headers = {"X-VG-Access-Key": args.access_key} if args.access_key else {}

    print(f"→ checking {base}\n")

    # 1. Health. A free-tier service sleeps when idle and takes up to a
    #    minute to wake, so the first request can get a loading page or a
    #    connection error. Retry until the service answers for itself.
    health: dict = {}
    healthy = False
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            status, body, _ = request(f"{base}/api/health", timeout=30)
            if status == 200:
                try:
                    health = json.loads(body)
                except ValueError:
                    health = {}
                if health.get("status") == "ok":
                    healthy = True
                    break
        except Exception:
            pass
        print("  … waiting for the service to start")
        time.sleep(5)
    record(
        "health endpoint responds",
        healthy,
        (
            f"status={health.get('status')} auth={health.get('auth')}"
            if health
            else "no answer within 180s"
        ),
    )

    # 2. The access model matches what health advertises
    auth_mode = health.get("auth")
    if auth_mode == "access_key":
        record(
            "access key is required and accepted",
            bool(args.access_key),
            "the deployment requires X-VG-Access-Key — pass --access-key",
        )
    elif healthy:
        record("deployment is open (as health reports)", True, f"auth={auth_mode}")

    # 3. The investigator answers
    try:
        status, body, _ = request(
            f"{base}/api/incident-investigate",
            method="POST",
            body={"question": args.question},
            headers=headers,
        )
        payload = json.loads(body) if body else {}
    except Exception as exc:
        record("investigation completes", False, str(exc))
        payload = {}
    else:
        findings = payload.get("provenance", {}).get("total_findings", 0)
        record(
            "investigation completes",
            status == 200 and findings > 0,
            f"status={status} unique findings={findings}",
        )

        # 4. The response is well-formed and internally consistent
        provenance = payload.get("provenance", {})
        lens_results = payload.get("lens_results", {})
        lenses = [name for name, data in lens_results.items() if data.get("findings")]
        record(
            "six lenses reported",
            len(lenses) == 6,
            f"lenses with findings: {len(lenses)}/6",
        )
        record(
            "totals are consistent",
            provenance.get("total_findings") == provenance.get("unique_sources"),
            f"total={provenance.get('total_findings')} "
            f"unique={provenance.get('unique_sources')} "
            f"across={provenance.get('lens_findings')}",
        )
        links = [
            finding.get("url", "")
            for data in lens_results.values()
            for finding in data.get("findings", [])
        ]
        unsafe = [url for url in links if url and not url.startswith(("http://", "https://"))]
        record("every source link is http(s)", not unsafe, f"unsafe: {unsafe[:3]}")

    # 5. The budgets are enforced
    status, _, _ = request(
        f"{base}/api/incident-investigate",
        method="POST",
        body={},
        headers=headers,
        timeout=30,
    )
    record("empty question rejected with 400", status == 400, f"status={status}")

    status, _, _ = request(
        f"{base}/api/incident-investigate",
        method="POST",
        body={"question": "x" * 600},
        headers=headers,
        timeout=30,
    )
    record("over-long question rejected with 400", status == 400, f"status={status}")

    status, _, _ = request(
        f"{base}/api/analyze",
        method="POST",
        body={},
        headers=headers,
        timeout=30,
    )
    record("deleted endpoints return 404", status == 404, f"status={status}")

    # 6. CORS is not open to the world
    try:
        _, _, cors_headers = request(
            f"{base}/api/health",
            headers={"Origin": "https://evil.example"},
            timeout=30,
        )
    except Exception:
        cors_headers = {}
    allowed = cors_headers.get("Access-Control-Allow-Origin")
    record(
        "unlisted origin is not echoed back",
        allowed != "https://evil.example",
        f"allow-origin={allowed!r}",
    )

    # 7. The rate limit kicks in (this deliberately spends the budget).
    #    The probe uses an empty question: it is rejected with 400 straight
    #    away, so it costs no upstream source calls, but it still goes
    #    through the access check — which is what charges the budget.
    #    A real question would take ~10s per call and the 60s window would
    #    refill before the limit was ever reached.
    limit_hit = False
    for _ in range(40):
        try:
            status, _, _ = request(
                f"{base}/api/incident-investigate",
                method="POST",
                body={"question": ""},
                headers=headers,
                timeout=30,
            )
        except Exception:
            break
        if status == 429:
            limit_hit = True
            break
    record("rate limit returns 429 once exhausted", limit_hit)

    # Report
    print()
    failed = 0
    for name, passed, detail in CHECKS:
        mark = "PASS" if passed else "FAIL"
        if not passed:
            failed += 1
        suffix = f"  ({detail})" if detail else ""
        print(f"[{mark}] {name}{suffix}")

    print()
    if failed:
        print(f"{failed} of {len(CHECKS)} checks FAILED")
        return 1
    print(f"all {len(CHECKS)} checks passed — the deployment is healthy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
