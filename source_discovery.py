#!/usr/bin/env python3
"""Conservative source discovery and verification for Community Finder.

The discovery job finds candidate public data sources, evaluates technical and
reuse signals, and writes a review/approval report. It never treats a public
web page as permission to scrape. Only high-confidence machine-readable,
explicitly reusable sources can be auto-enabled.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "discovery_config.json"
OUT = ROOT / "discovery_candidates.json"
UA = os.getenv("HARVEST_USER_AGENT", "CommunityFinderSourceDiscovery/1.0 (+source-discovery)")
TIMEOUT = 15
MAX_BYTES = 2_000_000


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
    government_signal: bool = False
    personal_data_risk: str = "unknown"
    score: int = 0
    decision: str = "needs_review"
    reasons: list[str] | None = None
    checked_at: str | None = None


def fetch(url: str, headers: dict[str, str] | None = None, max_bytes: int = MAX_BYTES):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
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
        clean = p._replace(fragment="").geturl()
        return clean.rstrip("/")
    except Exception:
        return None


def robots_ok(url: str) -> bool:
    p = urllib.parse.urlparse(url)
    robots = f"{p.scheme}://{p.netloc}/robots.txt"
    status, _, data = fetch(robots, max_bytes=250_000)
    if status is None:
        # Missing/unreachable robots is not permission, but is not a reason to
        # reject a clearly authorized API. Keep this as unknown/allowed here;
        # the final decision still requires explicit reuse evidence.
        return True
    text = data.decode("utf-8", "ignore")
    ua_block = False
    current = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        k, v = [x.strip().lower() for x in line.split(":", 1)]
        if k == "user-agent":
            current = v in {"*", "communityfinder", "communityfindersourcediscovery"}
        elif k == "disallow" and current and v:
            path = urllib.parse.urlparse(url).path or "/"
            if path.startswith(v):
                ua_block = True
    return not ua_block


def text_signals(url: str, body: bytes) -> tuple[bool, str | None, bool, str]:
    p = urllib.parse.urlparse(url)
    host = p.netloc.lower()
    text = body.decode("utf-8", "ignore")[:1_000_000].lower()
    government = any(x in host for x in (".gov", ".wa.gov", ".us"))
    machine = any(x in p.path.lower() for x in ("/api/", ".json", ".csv", ".xml", ".ics", "/export", "/query"))
    machine = machine or any(x in text[:5000] for x in ("application/json", "text/csv", "api endpoint", "soda api"))
    strong = [
        "creative commons", "cc by", "cc0", "open data", "open-data",
        "public domain", "data license", "reuse permitted", "permitted reuse",
        "api terms", "open government data", "open government licence",
    ]
    medium = ["terms of use", "terms of service", "license", "licence", "data use"]
    strong_hit = next((s for s in strong if s in text), None)
    medium_hit = next((s for s in medium if s in text), None)
    explicit = bool(strong_hit)
    terms = strong_hit or medium_hit
    # Conservative privacy signal. This does not prove absence of personal data.
    pii = "high" if any(x in text for x in ("social security", "ssn", "medical record", "patient record", "password")) else "unknown"
    return machine, terms, government, pii


def bing_search(query: str, count: int = 10) -> list[dict[str, str]]:
    key = os.getenv("BING_SEARCH_API_KEY")
    if not key:
        return []
    endpoint = "https://api.bing.microsoft.com/v7.0/search?" + urllib.parse.urlencode({"q": query, "count": count, "responseFilter": "Webpages"})
    status, headers, body = fetch(endpoint, {"Ocp-Apim-Subscription-Key": key}, 1_000_000)
    if status != 200:
        return []
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return []
    return [{"name": x.get("name", ""), "url": x.get("url", ""), "snippet": x.get("snippet", "")} for x in data.get("webPages", {}).get("value", [])]


def google_search(query: str, count: int = 10) -> list[dict[str, str]]:
    key, cx = os.getenv("GOOGLE_SEARCH_API_KEY"), os.getenv("GOOGLE_SEARCH_ENGINE_ID")
    if not key or not cx:
        return []
    endpoint = "https://www.googleapis.com/customsearch/v1?" + urllib.parse.urlencode({"key": key, "cx": cx, "q": query, "num": min(count, 10)})
    status, _, body = fetch(endpoint, max_bytes=1_000_000)
    if status != 200:
        return []
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return []
    return [{"name": x.get("title", ""), "url": x.get("link", ""), "snippet": x.get("snippet", "")} for x in data.get("items", [])]


def search(query: str) -> tuple[str, list[dict[str, str]]]:
    if os.getenv("BING_SEARCH_API_KEY"):
        return "bing", bing_search(query)
    if os.getenv("GOOGLE_SEARCH_API_KEY") and os.getenv("GOOGLE_SEARCH_ENGINE_ID"):
        return "google", google_search(query)
    return "none", []


def source_key(url: str) -> str:
    return "discovered-" + hashlib.sha256(url.encode()).hexdigest()[:16]


def evaluate(city: dict[str, Any], query: str, provider: str, item: dict[str, str]) -> Candidate | None:
    url = normalize_url(item.get("url", ""))
    if not url:
        return None
    status, headers, body = fetch(url)
    if status is None:
        return None
    machine, terms, gov, pii = text_signals(url, body)
    content_type = headers.get("Content-Type")
    machine = machine or bool(content_type and any(x in content_type.lower() for x in ("json", "csv", "xml", "calendar", "rss")))
    rb = robots_ok(url)
    score = 0
    reasons: list[str] = []
    if machine:
        score += 35; reasons.append("machine-readable/API/feed signal")
    if terms in {"creative commons", "cc by", "cc0", "public domain", "open data", "open-data", "data license", "reuse permitted", "permitted reuse", "open government data", "open government licence", "api terms"}:
        score += 40; reasons.append(f"explicit reuse signal: {terms}")
    elif terms:
        score += 10; reasons.append(f"terms/license page signal: {terms}")
    if gov:
        score += 15; reasons.append("government-domain signal")
    if rb:
        score += 5; reasons.append("robots policy does not block candidate URL")
    else:
        score -= 60; reasons.append("robots policy blocks candidate URL")
    if pii == "high":
        score -= 100; reasons.append("possible sensitive/personal-data signal")
    # Auto-enable only when both machine-readable and explicit reuse evidence exist.
    decision = "auto_approved" if score >= 85 and machine and bool(terms) and rb and pii != "high" else "needs_review"
    if decision == "needs_review":
        reasons.append("human review required before automation")
    return Candidate(
        source_key=source_key(url), name=item.get("name") or url, url=url,
        landing_url=item.get("url"), publisher=city.get("publisher"), city_key=city["city_key"],
        query=query, discovery_provider=provider, content_type=content_type, http_status=status,
        robots_allowed=rb, machine_readable=machine, explicit_reuse_signal=bool(terms),
        terms_signal=terms, government_signal=gov, personal_data_risk=pii, score=max(0, min(100, score)),
        decision=decision, reasons=reasons, checked_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )


def main() -> int:
    cfg = json.loads(CONFIG.read_text())
    all_candidates: dict[str, Candidate] = {}
    for city in cfg.get("cities", []):
        for query in city.get("queries", []):
            provider, results = search(query)
            for item in results:
                c = evaluate(city, query, provider, item)
                if c:
                    old = all_candidates.get(c.url)
                    if not old or c.score > old.score:
                        all_candidates[c.url] = c
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "search_configured": bool(os.getenv("BING_SEARCH_API_KEY") or (os.getenv("GOOGLE_SEARCH_API_KEY") and os.getenv("GOOGLE_SEARCH_ENGINE_ID"))),
        "candidates": [asdict(c) for c in sorted(all_candidates.values(), key=lambda x: (-x.score, x.city_key, x.name))],
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    auto = sum(1 for c in all_candidates.values() if c.decision == "auto_approved")
    review = len(all_candidates) - auto
    print(f"Discovered {len(all_candidates)} candidates: {auto} auto-approved, {review} review.")
    if not payload["search_configured"]:
        print("No search provider secret configured; known sources can still be harvested, but discovery is disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
