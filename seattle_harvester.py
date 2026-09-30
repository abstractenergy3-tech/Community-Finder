#!/usr/bin/env python3
"""Safe importer for the explicitly approved Seattle Emergency Food source."""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
USER_AGENT = os.environ.get(
    "HARVEST_USER_AGENT",
    "CommunityFinderHarvester/1.0 (+approved-source-harvest)",
)

SEATTLE_CITY_ID = "b47e66a8-465b-49a9-bc81-3d6e48a022fd"
SEATTLE_SOURCE_URL = (
    "https://cos-data.seattle.gov/api/v3/views/"
    "kkzf-ntnu/query.json?accessType=DOWNLOAD"
)
MAX_BYTES = 10_000_000
TIMEOUT = 30


def require_env() -> None:
    if not SUPABASE_URL or not SERVICE_KEY:
        raise SystemExit(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required"
        )


def request_json(
    url: str,
    method: str = "GET",
    payload: Any | None = None,
) -> tuple[int, dict[str, str], Any]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        url, data=data, method=method, headers=headers
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise RuntimeError("response exceeded safety size limit")
            parsed = json.loads(body.decode("utf-8")) if body else None
            return response.status, dict(response.headers), parsed
    except urllib.error.HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", "replace")
        raise RuntimeError(
            f"HTTP {exc.code} from {url}: {detail}"
        ) from exc


def supabase_request(
    table: str,
    query: str = "",
    method: str = "GET",
    payload: Any | None = None,
    prefer: str | None = None,
) -> Any:
    url = f"{SUPABASE_URL}/rest/v1/{table}{query}"
    headers = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    data = None

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if prefer:
        headers["Prefer"] = prefer

    req = urllib.request.Request(
        url, data=data, method=method, headers=headers
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            raw = response.read(MAX_BYTES)
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read(2000).decode("utf-8", "replace")
        raise RuntimeError(
            f"Supabase {method} {table} failed: HTTP {exc.code}: {detail}"
        ) from exc


def get_approved_source() -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "url": f"eq.{SEATTLE_SOURCE_URL}",
            "enabled": "eq.true",
            "allowed_automation": "eq.true",
            "select": "source_key,name,url,landing_url,publisher,"
            "enabled,allowed_automation",
            "limit": "1",
        }
    )
    rows = supabase_request("source_registry", f"?{params}")
    if not rows:
        raise RuntimeError(
            "Approved Seattle source was not found/enabled in source_registry"
        )
    return rows[0]


def clean(value: Any, limit: int = 2000) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", str(value)).strip()
    return value[:limit] if value else None


def first_value(row: dict[str, Any], names: tuple[str, ...]) -> Any:
    normalized = {
        re.sub(r"[^a-z0-9]+", "_", str(k).lower()).strip("_"): v
        for k, v in row.items()
    }
    for name in names:
        if name in normalized and normalized[name] not in (None, ""):
            return normalized[name]
    return None


def number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def parse_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = next(
            (
                payload[key]
                for key in ("data", "rows", "results", "items")
                if isinstance(payload.get(key), list)
            ),
            None,
        )
        if rows is None:
            raise RuntimeError(
                "Seattle endpoint returned JSON but no supported row array"
            )
    else:
        raise RuntimeError("Seattle endpoint returned an unsupported JSON shape")

    if not rows:
        raise RuntimeError(
            "Seattle endpoint returned zero rows; refusing to modify resources"
        )
    if not all(isinstance(row, dict) for row in rows):
        raise RuntimeError("Seattle endpoint contains non-object rows")
    return rows


def normalize_row(
    row: dict[str, Any],
    source: dict[str, Any],
    collected_at: str,
    expires_at: str,
) -> dict[str, Any] | None:
    title = clean(
        first_value(
            row,
            (
                "name", "program_name", "organization",
                "organization_name", "site_name", "location_name",
                "agency", "provider", "title",
            ),
        ),
        300,
    )
    if not title:
        return None

    description = clean(
        first_value(
            row,
            (
                "description", "details", "service_description",
                "program_description", "notes", "services",
            ),
        )
    )

    address = clean(
        first_value(
            row,
            (
                "address", "street_address", "site_address",
                "location", "address_1", "address1",
            ),
        ),
        500,
    )
    city = clean(first_value(row, ("city", "city_name")), 100)
    state = clean(first_value(row, ("state", "state_code")), 50)
    zip_code = clean(
        first_value(row, ("zip", "zipcode", "zip_code", "postal_code")),
        30,
    )
    full_address = ", ".join(
        part for part in (address, city, state, zip_code) if part
    ) or None
    
        # This first adapter is intentionally Seattle-only.
    # Some source rows do not populate the city field reliably,
    # so also verify that the address explicitly identifies Seattle.
    city_is_seattle = bool(
        city and city.strip().lower() == "seattle"
    )

    address_is_seattle = bool(
        address
        and re.search(
            r"\bSeattle\s*,?\s*WA\b",
            address,
            flags=re.IGNORECASE,
        )
    )

    if not (city_is_seattle or address_is_seattle):
        return None
        
    phone = clean(
        first_value(row, ("phone", "phone_number", "contact_phone", "telephone")),
        100,
    )
    website = clean(
        first_value(row, ("website", "url", "web", "website_url", "link")),
        1000,
    )
    hours = clean(
        first_value(
            row,
            ("hours", "hours_of_operation", "operating_hours", "schedule"),
        ),
        1000,
    )
    eligibility = clean(
        first_value(
            row,
            ("eligibility", "eligibility_requirements", "who_can_use"),
        ),
        1000,
    )
    cost = clean(
        first_value(row, ("cost", "fee", "fees", "price")),
        300,
    )

    latitude = number(first_value(row, ("latitude", "lat", "y")))
    longitude = number(
        first_value(row, ("longitude", "lon", "lng", "long", "x"))
    )

    raw_source = json.loads(json.dumps(row, ensure_ascii=False))
    canonical = json.dumps(
        raw_source,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    source_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return {
        "city_id": SEATTLE_CITY_ID,
        "title": title,
        "description": description,
        "category": "Food Assistance",
        "eligibility": eligibility,
        "address": full_address,
        "latitude": latitude,
        "longitude": longitude,
        "phone": phone,
        "website": website,
        "hours": hours,
        "cost": cost,
        "source_url": source["url"],
        "publisher": source.get("publisher"),
        "verification_state": "source-derived",
        "collected_at": collected_at,
        "expires_at": expires_at,
        "source_hash": source_hash,
        "raw_source": raw_source,
        "active": True,
    }


def existing_source_rows(source_url: str) -> dict[str, dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "source_url": f"eq.{source_url}",
            "select": "id,source_hash",
            "limit": "10000",
        }
    )
    rows = supabase_request("resources", f"?{params}")
    return {
        row["source_hash"]: row
        for row in rows
        if row.get("source_hash")
    }


def write_resources(
    rows: list[dict[str, Any]],
    existing: dict[str, dict[str, Any]],
) -> tuple[int, int]:
    inserted = 0
    updated = 0

    for row in rows:
        old = existing.get(row["source_hash"])
        if old:
            row_id = urllib.parse.quote(old["id"], safe="")
            supabase_request(
                "resources",
                f"?id=eq.{row_id}",
                method="PATCH",
                payload=row,
                prefer="return=minimal",
            )
            updated += 1
        else:
            supabase_request(
                "resources",
                "",
                method="POST",
                payload=row,
                prefer="return=minimal",
            )
            inserted += 1

    return inserted, updated


def main() -> int:
    require_env()

    source = get_approved_source()
    print(f"Approved source: {source.get('name')}")

    status, headers, payload = request_json(SEATTLE_SOURCE_URL)
    content_type = headers.get("Content-Type", "")
    if status != 200:
        raise RuntimeError(f"Seattle source returned HTTP {status}")
    if "json" not in content_type.lower():
        raise RuntimeError(
            f"Seattle source returned unexpected content type: {content_type}"
        )

    raw_rows = parse_rows(payload)
    collected = datetime.now(timezone.utc)
    expires = collected + timedelta(hours=48)

    normalized = []
    skipped = 0

    for raw in raw_rows:
        item = normalize_row(
            raw,
            source,
            collected.isoformat(),
            expires.isoformat(),
        )
        if item:
            normalized.append(item)
        else:
            skipped += 1

    if not normalized:
        raise RuntimeError(
            "No usable resource rows were produced; refusing to write"
        )

    existing = existing_source_rows(source["url"])
    inserted, updated = write_resources(normalized, existing)

    print(
        f"Harvest complete: {inserted} inserted, {updated} updated, "
        f"{skipped} skipped from {len(raw_rows)} source rows."
    )
    print("No arbitrary web scraping was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
