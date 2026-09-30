"""
Reusable harvesting utilities for Community Finder.

This module contains the shared, source-agnostic parts of harvesting:
- HTTP fetching
- response validation
- record normalization helpers
- deterministic hashing
- safe Supabase resource synchronization

Source-specific adapters should remain responsible for:
- choosing an approved source
- understanding that source's field names
- applying source-specific geography rules
- deciding which records are actually eligible for import
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Optional

import requests


DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RESPONSE_BYTES = 10 * 1024 * 1024
DEFAULT_USER_AGENT = "CommunityFinderHarvester/1.0"


class HarvestError(RuntimeError):
    """Raised when a harvest cannot safely continue."""


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def isoformat_utc(value: datetime) -> str:
    """Return an ISO-8601 UTC timestamp."""
    return value.astimezone(timezone.utc).isoformat()


def get_env(name: str) -> str:
    """Read a required environment variable."""
    value = os.getenv(name)

    if not value:
        raise HarvestError(f"Required environment variable is missing: {name}")

    return value


def fetch_json(
    url: str,
    *,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> Any:
    """
    Fetch a JSON resource with conservative safety checks.

    This function is intentionally generic. It does not discover URLs
    and does not bypass robots.txt, authentication, rate limits, or
    source-specific restrictions.
    """
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        raise HarvestError(f"Source request failed: {exc}") from exc

    if response.status_code != 200:
        raise HarvestError(
            f"Source returned HTTP {response.status_code}: {url}"
        )

    content_type = response.headers.get("Content-Type", "").lower()

    if "json" not in content_type:
        raise HarvestError(
            f"Source did not return JSON content: {content_type or 'unknown'}"
        )

    content_length = response.headers.get("Content-Length")

    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise HarvestError(
                    f"Source response exceeds {max_bytes} bytes."
                )
        except ValueError:
            pass

    body = response.content

    if len(body) > max_bytes:
        raise HarvestError(
            f"Source response exceeds {max_bytes} bytes."
        )

    try:
        return response.json()
    except ValueError as exc:
        raise HarvestError("Source returned invalid JSON.") from exc


def extract_rows(payload: Any) -> list[dict[str, Any]]:
    """
    Convert common API response shapes into a list of objects.

    Supported:
    - top-level list
    - {"data": [...]}
    - {"rows": [...]}
    - {"results": [...]}
    - {"items": [...]}
    """
    if isinstance(payload, list):
        rows = payload

    elif isinstance(payload, dict):
        rows = None

        for key in ("data", "rows", "results", "items"):
            candidate = payload.get(key)

            if isinstance(candidate, list):
                rows = candidate
                break

        if rows is None:
            raise HarvestError(
                "JSON response did not contain a supported record list."
            )

    else:
        raise HarvestError(
            "JSON response must be an object or list."
        )

    if not rows:
        raise HarvestError("Source returned zero records.")

    if not all(isinstance(row, dict) for row in rows):
        raise HarvestError(
            "Source returned records that are not JSON objects."
        )

    return rows


def clean_text(value: Any) -> Optional[str]:
    """Convert a value to normalized text, or None."""
    if value is None:
        return None

    text = str(value).strip()

    return text or None


def first_value(
    row: dict[str, Any],
    *field_names: str,
) -> Optional[str]:
    """Return the first non-empty value among candidate fields."""
    for field_name in field_names:
        value = clean_text(row.get(field_name))

        if value:
            return value

    return None


def normalize_url(value: Any) -> Optional[str]:
    """Normalize a URL-like value without attempting to fetch it."""
    value = clean_text(value)

    if not value:
        return None

    if value.startswith(("http://", "https://")):
        return value

    return None


def normalize_record(
    *,
    row: dict[str, Any],
    source_url: str,
    publisher: Optional[str],
    city_id: str,
    category: Optional[str],
    title_fields: tuple[str, ...],
    source_record_id_fields: tuple[str, ...] = (),
    description_fields: tuple[str, ...] = (),
    address_fields: tuple[str, ...] = (),
    phone_fields: tuple[str, ...] = (),
    website_fields: tuple[str, ...] = (),
    hours_fields: tuple[str, ...] = (),
    eligibility_fields: tuple[str, ...] = (),
    cost_fields: tuple[str, ...] = (),
    latitude_fields: tuple[str, ...] = (),
    longitude_fields: tuple[str, ...] = (),
    expires_hours: int = 48,
) -> dict[str, Any]:
    """
    Convert one source row into the Community Finder resource shape.

    Source-specific adapters provide field-name mappings. This function
    does not guess geography or eligibility.
    """
    title = first_value(row, *title_fields)

    if not title:
        raise HarvestError(
            "A source record is missing a usable title."
        )
        
    source_record_id = first_value(row, *source_record_id_fields)

    if not source_record_id:
        raise HarvestError(
            "A source record is missing a stable source_record_id."
        )
    
    latitude = first_value(row, *latitude_fields)
    longitude = first_value(row, *longitude_fields)

    try:
        latitude_value = float(latitude) if latitude else None
    except ValueError:
        latitude_value = None

    try:
        longitude_value = float(longitude) if longitude else None
    except ValueError:
        longitude_value = None

    collected_at = utc_now()
    expires_at = collected_at + timedelta(hours=expires_hours)

    return {
        "city_id": city_id,
        "title": title,
        "source_record_id": source_record_id,
        "description": first_value(row, *description_fields),
        "category": category,
        "eligibility": first_value(row, *eligibility_fields),
        "address": first_value(row, *address_fields),
        "latitude": latitude_value,
        "longitude": longitude_value,
        "phone": first_value(row, *phone_fields),
        "website": normalize_url(
            first_value(row, *website_fields)
        ),
        "hours": first_value(row, *hours_fields),
        "cost": first_value(row, *cost_fields),
        "source_url": source_url,
        "publisher": publisher,
        "verification_state": "source-derived",
        "collected_at": isoformat_utc(collected_at),
        "expires_at": isoformat_utc(expires_at),
        "source_hash": source_hash(row),
        "raw_source": row,
        "active": True,
    }


def canonical_json(value: Any) -> str:
    """Create deterministic JSON for hashing."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def source_hash(row: dict[str, Any]) -> str:
    """Return a stable SHA-256 hash for a source record."""
    payload = canonical_json(row).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()


def build_supabase_headers(service_role_key: str) -> dict[str, str]:
    """Build headers for server-side Supabase REST calls."""
    return {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }


def supabase_request(
    method: str,
    url: str,
    *,
    service_role_key: str,
    json_body: Any = None,
    params: Optional[dict[str, str]] = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> requests.Response:
    """Make a server-side Supabase REST request."""
    headers = build_supabase_headers(service_role_key)

    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        raise HarvestError(
            f"Supabase request failed: {exc}"
        ) from exc

    if response.status_code >= 400:
        raise HarvestError(
            f"Supabase returned HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    return response


def get_source_registry_entry(
    *,
    supabase_url: str,
    service_role_key: str,
    source_url: str,
) -> dict[str, Any]:
    """
    Confirm that a source is explicitly enabled for automation.

    This is an important safety boundary: being given a URL is not enough.
    The source must also exist in source_registry and be enabled.
    """
    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/source_registry"

    response = supabase_request(
        "GET",
        endpoint,
        service_role_key=service_role_key,
        params={
            "url": f"eq.{source_url}",
            "enabled": "eq.true",
            "allowed_automation": "eq.true",
            "select": "*",
        },
    )

    rows = response.json()

    if not rows:
        raise HarvestError(
            "Source is not enabled for automated harvesting."
        )

    return rows[0]


def upsert_resource(
    *,
    supabase_url: str,
    service_role_key: str,
    resource: dict[str, Any],
    existing_id: Optional[str] = None,
) -> str:
    """
    Insert or update one resource.

    Existing records are updated by ID. New records are inserted.
    """
    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/resources"

    if existing_id:
        response = supabase_request(
            "PATCH",
            endpoint,
            service_role_key=service_role_key,
            params={
                "id": f"eq.{existing_id}",
            },
            json_body=resource,
        )

        return existing_id

    headers = build_supabase_headers(service_role_key)
    headers["Prefer"] = "return=representation"

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=resource,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise HarvestError(
            f"Supabase insert failed: {exc}"
        ) from exc

    if response.status_code >= 400:
        raise HarvestError(
            f"Supabase insert returned HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    inserted = response.json()

    if not inserted:
        raise HarvestError(
            "Supabase insert succeeded but returned no resource."
        )

    return inserted[0]["id"]


def synchronize_resources(
    *,
    supabase_url: str,
    service_role_key: str,
    source_url: str,
    resources: Iterable[dict[str, Any]],
    on_resource: Optional[
        Callable[[dict[str, Any]], None]
    ] = None,
) -> dict[str, int]:
    """
    Synchronize normalized resources for one approved source.

    source_record_id identifies the source record.
    source_hash identifies the current content/version.

    Same source_record_id + same hash:
        unchanged

    Same source_record_id + changed hash:
        update existing resource

    New source_record_id:
        insert new resource

    Missing source_record_id:
        fail closed

    Missing source rows are deliberately NOT deactivated.
    """
    resources = list(resources)

    if not resources:
        raise HarvestError(
            "Refusing to synchronize zero normalized resources."
        )

    # Every normalized resource must have a stable source identity.
    seen_ids: set[str] = set()

    for resource in resources:
        source_record_id = resource.get("source_record_id")

        if not source_record_id:
            raise HarvestError(
                "Refusing to synchronize a resource without "
                "source_record_id."
            )

        if source_record_id in seen_ids:
            raise HarvestError(
                "Duplicate source_record_id in current harvest: "
                f"{source_record_id}"
            )

        seen_ids.add(source_record_id)

    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/resources"

    response = supabase_request(
        "GET",
        endpoint,
        service_role_key=service_role_key,
        params={
            "source_url": f"eq.{source_url}",
            "select": "id,source_hash,source_record_id",
        },
    )

    existing_rows = response.json()

    existing_by_id: dict[str, dict[str, Any]] = {}

    for row in existing_rows:
        source_record_id = row.get("source_record_id")

        if not source_record_id:
            # Legacy rows created before stable source identity.
            continue

        if source_record_id in existing_by_id:
            raise HarvestError(
                "Duplicate source_record_id already exists in "
                f"resources: {source_record_id}"
            )

        existing_by_id[source_record_id] = row

    stats = {
        "received": len(resources),
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
    }

    for resource in resources:
        source_record_id = resource["source_record_id"]
        existing = existing_by_id.get(source_record_id)

        if existing:
            if existing.get("source_hash") == resource.get("source_hash"):
                stats["unchanged"] += 1

                if on_resource:
                    on_resource(resource)

                continue

            upsert_resource(
                supabase_url=supabase_url,
                service_role_key=service_role_key,
                resource=resource,
                existing_id=existing["id"],
            )

            stats["updated"] += 1

        else:
            upsert_resource(
                supabase_url=supabase_url,
                service_role_key=service_role_key,
                resource=resource,
            )

            stats["inserted"] += 1

        if on_resource:
            on_resource(resource)

    return stats
