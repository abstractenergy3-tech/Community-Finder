```python
#!/usr/bin/env python3
"""Conservative source verification for Community Finder.

This verifier uses a curated known-source list instead of an external
web-search API. It verifies technical, reuse, robots, and data-sensitivity
signals without treating public visibility as permission to scrape.

Important:
- This is an engineering safety filter, not legal advice.
- Explicit reuse evidence is still required for automatic approval.
- High or unclear personal-data risk remains a human-review condition.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
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

UA = os.getenv(
    "HARVEST_USER_AGENT",
    "CommunityFinderSourceDiscovery/1.0 (+source-discovery)",
)

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
    personal_data_triggers: list[str] | None = None
    score: int = 0
    decision: str = "needs_review"
    reasons: list[str] | None = None
    checked_at: str | None = None


def fetch(url: str, max_bytes: int = MAX_BYTES):
    """Fetch a URL with a bounded response size."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            data = response.read(max_bytes + 1)
            return response.status, response.headers, data[:max_bytes]

    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
    ):
        return None, {}, b""


def normalize_url(url: str) -> str | None:
    try:
        parsed = urllib.parse.urlparse(url)

        if parsed.scheme not in {"http", "https"}:
            return None

        if not parsed.netloc:
            return None

        return parsed._replace(fragment="").geturl().rstrip("/")

    except Exception:
        return None


def robots_ok(url: str) -> bool:
    """Return whether robots.txt appears not to block this candidate URL.

    An unavailable robots.txt is treated as allowed for this engineering
    check, but this is NOT legal permission to scrape.
    """
    parsed = urllib.parse.urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    status, _, data = fetch(
        robots_url,
        max_bytes=ROBOTS_MAX_BYTES,
    )

    if status is None:
        return True

    text = data.decode("utf-8", "ignore")

    current = False
    path = parsed.path or "/"

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()

        if not line or ":" not in line:
            continue

        key, value = [
            item.strip().lower()
            for item in line.split(":", 1)
        ]

        if key == "user-agent":
            current = value in {
                "*",
                "communityfinder",
                "communityfindersourcediscovery",
            }

        elif (
            key == "disallow"
            and current
            and value
            and path.startswith(value)
        ):
            return False

    return True


def _contains_sensitive_pattern(text: str, pattern: str) -> bool:
    """Case-insensitive regex search helper."""
    return bool(re.search(pattern, text, flags=re.IGNORECASE))


def personal_data_check(
    url: str,
    body: bytes,
    content_type: str | None,
) -> tuple[str, list[str]]:
    """Classify likely personal-data exposure conservatively.

    We do NOT classify a source as high-risk merely because ordinary words
    such as 'contact', 'address', 'phone', or 'email' appear.

    High-risk requires stronger evidence of sensitive individual-level data,
    such as explicit medical records, Social Security numbers, passwords,
    financial account information, or similar sensitive identifiers.

    Generic organization/service contact information remains unknown rather
    than being treated as high risk.

    Unknown is intentionally NOT auto-approved.
    """
    text = body.decode("utf-8", "ignore")[:1_000_000]

    triggers: list[str] = []

    sensitive_patterns = [
        (
            "social_security_number",
            r"\b(?:social\s+security|ssn)\b",
        ),
        (
            "medical_or_patient_record",
            r"\b(?:medical\s+record|patient\s+record|patient\s+id)\b",
        ),
        (
            "password_or_secret",
            r"\b(?:password|passwd|secret\s+key|private\s+key)\b",
        ),
        (
            "financial_account_data",
            r"\b(?:bank\s+account|routing\s+number|credit\s+card\s+number)\b",
        ),
        (
            "government_person_identifier",
            r"\b(?:driver'?s\s+license\s+number|passport\s+number)\b",
        ),
    ]

    for name, pattern in sensitive_patterns:
        if _contains_sensitive_pattern(text, pattern):
            triggers.append(name)

    if triggers:
        return "high", triggers

    # We deliberately do not infer low risk solely from public accessibility.
    # If no strong sensitive-data evidence is present, classify as unknown.
    return "unknown", triggers


def signals(
    url: str,
    body: bytes,
    content_type: str | None = None,
):
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()

    text = body.decode("utf-8", "ignore")[:1_000_000].lower()

    government = any(
        host.endswith(suffix)
        for suffix in (
            ".gov",
            ".wa.gov",
            ".us",
        )
    )

    machine = any(
        marker in parsed.path.lower()
        for marker in (
            "/api/",
            ".json",
            ".csv",
            ".xml",
            ".ics",
            "/export",
            "/query",
        )
    )

    if content_type:
        lowered_content_type = content_type.lower()

        machine = machine or any(
            marker in lowered_content_type
            for marker in (
                "json",
                "csv",
                "xml",
                "calendar",
                "rss",
            )
        )

    machine = machine or any(
        marker in text[:5000]
        for marker in (
            "application/json",
            "text/csv",
            "api endpoint",
            "soda api",
        )
    )

    strong_terms = [
        "creative commons",
        "cc by",
        "cc0",
        "open data",
        "open-data",
        "public domain",
        "data license",
        "reuse permitted",
        "permitted reuse",
        "api terms",
        "open government data",
        "open government licence",
    ]

    medium_terms = [
        "terms of use",
        "terms of service",
        "license",
        "licence",
        "data use",
    ]

    strong_hit = next(
        (term for term in strong_terms if term in text),
        None,
    )

    medium_hit = next(
        (term for term in medium_terms if term in text),
        None,
    )

    terms = strong_hit or medium_hit

    pii, triggers = personal_data_check(
        url,
        body,
        content_type,
    )

    return (
        machine,
        terms,
        government,
        pii,
        triggers,
    )


def load_json(
    path: Path,
    default: dict[str, Any],
) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8")
        )

        return (
            value
            if isinstance(value, dict)
            else default
        )

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return default


def source_key(url: str) -> str:
    return (
        "discovered-"
        + hashlib.sha256(
            url.encode("utf-8")
        ).hexdigest()[:16]
    )


def evaluate(
    city: dict[str, Any],
    query: str,
    item: dict[str, Any],
) -> Candidate | None:
    url = normalize_url(
        str(item.get("url", ""))
    )

    if not url:
        return None

    status, headers, body = fetch(url)

    if status is None:
        return None

    content_type = headers.get("Content-Type")

    (
        machine,
        _,
        gov,
        pii,
        pii_triggers,
    ) = signals(
        url,
        body,
        content_type,
    )

    rb = robots_ok(url)

    reasons: list[str] = []
    score = 0

    if machine:
        score += 35
        reasons.append(
            "machine-readable/API/feed signal"
        )

    if gov:
        score += 15
        reasons.append(
            "government-domain signal"
        )

    if rb:
        score += 5
        reasons.append(
            "robots policy does not block candidate URL"
        )
    else:
        score -= 60
        reasons.append(
            "robots policy blocks candidate URL"
        )

    if pii == "high":
        score -= 100

        if pii_triggers:
            reasons.append(
                "high-risk sensitive-data signal: "
                + ", ".join(pii_triggers)
            )
        else:
            reasons.append(
                "high-risk sensitive-data signal"
            )

    elif pii == "unknown":
        reasons.append(
            "no strong sensitive-data pattern confirmed; "
            "personal-data status remains unknown"
        )

    # Reuse evidence is checked separately from the data endpoint.
    evidence_url = (
        normalize_url(
            str(item.get("reuse_evidence_url", ""))
        )
        if item.get("reuse_evidence_url")
        else None
    )

    terms = None

    if evidence_url:
        (
            evidence_status,
            evidence_headers,
            evidence_body,
        ) = fetch(evidence_url)

        if evidence_status:
            (
                _,
                terms,
                _,
                _,
                _,
            ) = signals(
                evidence_url,
                evidence_body,
                evidence_headers.get("Content-Type"),
            )

            if terms:
                score += 40
                reasons.append(
                    "explicit reuse/terms signal from "
                    f"configured evidence: {terms}"
                )
            else:
                reasons.append(
                    "configured reuse evidence URL did not "
                    "expose a recognizable reuse/license signal"
                )

        else:
            reasons.append(
                "configured reuse evidence URL could not "
                "be verified"
            )

    else:
        reasons.append(
            "no explicit reuse evidence URL configured"
        )

    explicit = bool(terms)

    # Conservative approval rule:
    # - strong technical signal
    # - explicit reuse evidence
    # - robots does not block
    # - no confirmed high-risk personal data
    #
    # Unknown personal-data status does NOT automatically approve.
    decision = (
        "auto_approved"
        if (
            score >= 85
            and machine
            and explicit
            and rb
            and pii == "unknown"
        )
        else "needs_review"
    )

    if decision == "needs_review":
        reasons.append(
            "human review required before automation"
        )

    return Candidate(
        source_key=source_key(url),
        name=str(
            item.get("name")
            or url
        ),
        url=url,
        landing_url=item.get("landing_url"),
        publisher=(
            item.get("publisher")
            or city.get("publisher")
        ),
        city_key=str(
            city["city_key"]
        ),
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
        personal_data_triggers=pii_triggers,
        score=max(
            0,
            min(100, score),
        ),
        decision=decision,
        reasons=reasons,
        checked_at=time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        ),
    )


def main() -> int:
    cfg = load_json(
        CONFIG,
        {"cities": []},
    )

    known = load_json(
        KNOWN,
        {"sources": []},
    ).get(
        "sources",
        [],
    )

    candidates: dict[str, Candidate] = {}

    for city in cfg.get("cities", []):
        for query in city.get("queries", []):
            for item in known:
                if query not in item.get(
                    "queries",
                    [],
                ):
                    continue

                candidate = evaluate(
                    city,
                    query,
                    item,
                )

                if (
                    candidate
                    and (
                        candidate.url not in candidates
                        or candidate.score
                        > candidates[
                            candidate.url
                        ].score
                    )
                ):
                    candidates[
                        candidate.url
                    ] = candidate

    payload = {
        "generated_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        ),
        "search_configured": False,
        "discovery_mode": "known_sources_only",
        "candidates": [
            asdict(candidate)
            for candidate in sorted(
                candidates.values(),
                key=lambda item: (
                    -item.score,
                    item.city_key,
                    item.name,
                ),
            )
        ],
    }

    OUT.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    auto = sum(
        candidate.decision == "auto_approved"
        for candidate in candidates.values()
    )

    print(
        f"Verified {len(candidates)} known sources: "
        f"{auto} auto-approved, "
        f"{len(candidates) - auto} review."
    )

    print(
        "No external search API is required "
        "in this version."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```
