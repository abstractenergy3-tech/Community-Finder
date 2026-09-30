#!/usr/bin/env python3
"""Upload source-discovery results to Supabase using a service-role secret.

The service-role key must only exist in CI secrets/environment variables.
"""
from __future__ import annotations
import json, os, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
INPUT = ROOT / "discovery_candidates.json"

if not SUPABASE_URL or not SERVICE_KEY:
    raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

payload = json.loads(INPUT.read_text())
rows = []
for c in payload.get("candidates", []):
    rows.append({
        "source_key": c["source_key"], "name": c["name"], "url": c["url"],
        "landing_url": c.get("landing_url"), "publisher": c.get("publisher"),
        "city_key": c.get("city_key"), "discovery_provider": c.get("discovery_provider"),
        "discovery_query": c.get("query"), "score": c.get("score"),
        "decision": c.get("decision", "needs_review"),
        "checks": {
            "http_status": c.get("http_status"), "content_type": c.get("content_type"),
            "robots_allowed": c.get("robots_allowed"), "machine_readable": c.get("machine_readable"),
            "explicit_reuse_signal": c.get("explicit_reuse_signal"), "terms_signal": c.get("terms_signal"),
            "reuse_evidence_url": c.get("reuse_evidence_url"),
            "government_signal": c.get("government_signal"), "personal_data_risk": c.get("personal_data_risk")
        },
        "reasons": c.get("reasons", []), "last_checked_at": c.get("checked_at")
    })
if not rows:
    print("No discovered candidates to upload.")
    raise SystemExit(0)

url = f"{SUPABASE_URL}/rest/v1/source_candidates?on_conflict=url"
req = urllib.request.Request(url, data=json.dumps(rows).encode(), method="POST", headers={
    "apikey": SERVICE_KEY,
    "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"
})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        if r.status >= 300:
            raise RuntimeError(f"Supabase returned HTTP {r.status}")
except Exception as e:
    raise SystemExit(f"Candidate upload failed: {e}")

print(f"Uploaded {len(rows)} source candidates.")

auto_rows = []
for c in payload.get("candidates", []):
    if c.get("decision") != "auto_approved":
        continue
    auto_rows.append({
        "source_key": c["source_key"], "name": c["name"], "url": c["url"],
        "landing_url": c.get("landing_url"), "publisher": c.get("publisher"),
        "license_status": "auto_verified_candidate", "allowed_automation": True,
        "attribution_required": False, "refresh_hours": 24, "enabled": True,
        "discovery_status": "auto_approved", "discovery_score": c.get("score"),
        "discovery_checks": {
            "http_status": c.get("http_status"), "content_type": c.get("content_type"),
            "robots_allowed": c.get("robots_allowed"), "machine_readable": c.get("machine_readable"),
            "explicit_reuse_signal": c.get("explicit_reuse_signal"), "terms_signal": c.get("terms_signal"),
            "reuse_evidence_url": c.get("reuse_evidence_url"),
            "government_signal": c.get("government_signal"), "personal_data_risk": c.get("personal_data_risk")
        },
        "discovered_at": c.get("checked_at"), "last_verified_at": c.get("checked_at"),
        "verification_notes": "; ".join(c.get("reasons", [])), "discovery_query": c.get("query"),
        "automation_mode": "automatic"
    })

if auto_rows:
    source_url = f"{SUPABASE_URL}/rest/v1/source_registry?on_conflict=source_key"
    req = urllib.request.Request(source_url, data=json.dumps(auto_rows).encode(), method="POST", headers={
        "apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status >= 300:
                raise RuntimeError(f"Supabase returned HTTP {r.status}")
    except Exception as e:
        raise SystemExit(f"Auto-approved source registry update failed: {e}")
    print(f"Auto-enabled {len(auto_rows)} high-confidence sources.")
else:
    print("No sources met the strict auto-approval threshold.")
