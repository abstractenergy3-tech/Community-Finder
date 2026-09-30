#!/usr/bin/env python3
"""Conservative source verification for Community Finder.

This version intentionally uses a curated known-source list instead of an
external web-search API. It verifies technical and reuse signals but does not
assume that a publicly reachable page is permission to scrape.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "discovery_config.json"
KNOWN = ROOT / "known_sources.json"
OUT = ROOT / "discovery_candidates.json"
UA = os.getenv("HARVEST_USER_AGENT", "CommunityFinderSourceDiscovery/1.0 (+source-discovery)")
TIMEOUT = 15
MAX_BYTES = 2_000_000
ROBOTS_MAX_BYTES = 250_000


@dataclass
class Candidate:
    source_key: str
    name: str
    url: str
    landing_url: str | None
    publisher: str | None
    city_key: str
    query: str
    discovery_provider: str
    content_type: str | None = None
    http_status: int | None = None
    robots_allowed: bool | None = None
    machine_readable: bool = False
    explicit_reuse_signal: bool = False
    terms_signal: str | None = None
    reuse_evidence_url: str | None = None
    government_signal: bool = False
    personal_data_risk: str = "unknown"
    score: int = 0
    decision: str = "needs_review"
    reasons: list[str] | None = None
    checked_at: str | None = None


def fetch(url: str, max_bytes: int = MAX_BYTES):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = r.read(max_bytes + 1)
            return r.status, r.headers, data[:max_bytes]
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None, {}, b""


def normalize_url(url: str) -> str | None:
    try:
        p = urllib.parse.urlparse(url)
        if p.scheme not in {"http", "https"} or not p.netloc:
            return None
        return p._replace(fragment="").geturl().rstrip("/")
    except Exception:
        return None


def robots_ok(url: str) -> bool:
    p = urllib.parse.urlparse(url)
    robots = f"{p.scheme}://{p.netloc}/robots.txt"
    status, _, data = fetch(robots, max_bytes=ROBOTS_MAX_BYTES)
    if status is None:
        # Unknown robots state is not legal permission. This verifier remains
        # conservative because auto-approval also requires explicit reuse evidence.
        return True
    text = data.decode("utf-8", "ignore")
    current = False
    path = p.path or "/"
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = [x.strip().lower() for x in line.split(":", 1)]
        if key == "user-agent":
            current = value in {"*", "communityfinder", "communityfindersourcediscovery"}
        elif key == "disallow" and current and value and path.startswith(value):
            return False
    return True


def signals(url: str, body: bytes, content_type: str | None = None):
    p = urllib.parse.urlparse(url)
    host = p.netloc.lower()
    text = body.decode("utf-8", "ignore")[:1_000_000].lower()
    government = any(host.endswith(suffix) for suffix in (".gov", ".wa.gov", ".us"))
    machine = any(x in p.path.lower() for x in ("/api/", ".json", ".csv", ".xml", ".ics", "/export", "/query"))
    if content_type:
        machine = machine or any(x in content_type.lower() for x in ("json", "csv", "xml", "calendar", "rss"))
    machine = machine or any(x in text[:5000] for x in ("application/json", "text/csv", "api endpoint", "soda api"))

    strong = [
        "creative commons", "cc by", "cc0", "open data", "open-data",
        "public domain", "data license", "reuse permitted", "permitted reuse",
        "api terms", "open government data", "open government licence",
    ]
    medium = ["terms of use", "terms of service", "license", "licence", "data use"]
    strong_hit = next((s for s in strong if s in text), None)
    medium_hit = next((s for s in medium if s in text), None)
    terms = strong_hit or medium_hit
    pii = "high" if any(x in text for x in ("social security", "ssn", "medical record", "patient record", "password")) else "unknown"
    return machine, terms, government, pii


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else default
    except (OSError, json.JSONDecodeError):
        return default


def source_key(url: str) -> str:
    return "discovered-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def evaluate(city: dict[str, Any], query: str, item: dict[str, Any]) -> Candidate | None:
    url = normalize_url(str(item.get("url", "")))
    if not url:
        return None

    status, headers, body = fetch(url)
    if status is None:
        return None

    content_type = headers.get("Content-Type")
    machine, _, gov, pii = signals(url, body, content_type)
    rb = robots_ok(url)
    reasons: list[str] = []
    score = 0

    if machine:
        score += 35
        reasons.append("machine-readable/API/feed signal")
    if gov:
        score += 15
        reasons.append("government-domain signal")
    if rb:
        score += 5
        reasons.append("robots policy does not block candidate URL")
    else:
        score -= 60
        reasons.append("robots policy blocks candidate URL")
    if pii == "high":
        score -= 100
        reasons.append("possible sensitive/personal-data signal")

    # Reuse evidence is deliberately checked separately from the data endpoint.
    # A generic landing page or a public API response is not enough by itself.
    evidence_url = normalize_url(str(item.get("reuse_evidence_url", ""))) if item.get("reuse_evidence_url") else None
    terms = None
    if evidence_url:
        evidence_status, evidence_headers, evidence_body = fetch(evidence_url)
        if evidence_status:
            _, terms, _, _ = signals(evidence_url, evidence_body, evidence_headers.get("Content-Type"))
            if terms:
                score += 40
                reasons.append(f"explicit reuse/terms signal from configured evidence: {terms}")
            else:
                reasons.append("configured reuse evidence URL did not expose a recognizable reuse/license signal")
        else:
            reasons.append("configured reuse evidence URL could not be verified")
    else:
        reasons.append("no explicit reuse evidence URL configured")

    explicit = bool(terms)
    decision = "auto_approved" if score >= 85 and machine and explicit and rb and pii != "high" else "needs_review"
    if decision == "needs_review":
        reasons.append("human review required before automation")

    return Candidate(
        source_key=source_key(url),
        name=str(item.get("name") or url),
        url=url,
        landing_url=item.get("landing_url"),
        publisher=item.get("publisher") or city.get("publisher"),
        city_key=str(city["city_key"]),
        query=query,
        discovery_provider="known_source",
        content_type=content_type,
        http_status=status,
        robots_allowed=rb,
        machine_readable=machine,
        explicit_reuse_signal=explicit,
        terms_signal=terms,
        reuse_evidence_url=evidence_url,
        government_signal=gov,
        personal_data_risk=pii,
        score=max(0, min(100, score)),
        decision=decision,
        reasons=reasons,
        checked_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )


def main() -> int:
    cfg = load_json(CONFIG, {"cities": []})
    known = load_json(KNOWN, {"sources": []}).get("sources", [])
    candidates: dict[str, Candidate] = {}

    for city in cfg.get("cities", []):
        for query in city.get("queries", []):
            for item in known:
                if query not in item.get("queries", []):
                    continue
                candidate = evaluate(city, query, item)
                if candidate and (candidate.url not in candidates or candidate.score > candidates[candidate.url].score):
                    candidates[candidate.url] = candidate

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "search_configured": False,
        "discovery_mode": "known_sources_only",
        "candidates": [
            asdict(c) for c in sorted(candidates.values(), key=lambda x: (-x.score, x.city_key, x.name))
        ],
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    auto = sum(c.decision == "auto_approved" for c in candidates.values())
    print(f"Verified {len(candidates)} known sources: {auto} auto-approved, {len(candidates) - auto} review.")
    print("No external search API is required in this version.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
