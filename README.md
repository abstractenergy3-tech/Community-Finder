# Community Finder — MVP prototype

## What this is
A phone-friendly Progressive Web App prototype for discovering local resources, programs, and community activities.

## Current prototype
- Search
- Category filter
- Cost filter
- Time filter
- Browser location permission
- Mobile-first interface
- Sample listings only

## Production architecture
Recommended path:
- Front end: React Native/Expo for Android + iOS, or PWA for the fastest first launch.
- Backend: Supabase (Postgres + authentication + storage) or Firebase.
- Maps/geocoding: MapLibre/Google Maps depending on budget and licensing.
- Data ingestion: permitted public APIs, government/open-data feeds, organization submissions, and carefully controlled website imports.
- Search: Postgres full-text search initially; dedicated search service later if needed.
- Moderation: admin review queue + user reports + freshness timestamps.

## Core data model
Organizations:
id, name, description, website, phone, email, verified_at, source_url

Resources:
id, organization_id, title, description, category, cost_type, eligibility,
address, latitude, longitude, phone, website, start_at, end_at,
recurrence, source_url, last_verified_at, status

Users:
id, saved_resources, notification_preferences

Reports:
id, resource_id, user_id, reason, details, created_at, status

## Discovery flow
1. User chooses location or enters ZIP code.
2. App finds resources within a radius.
3. Search/filter is applied.
4. Results are ranked by distance, freshness, relevance, and verification status.
5. User opens a listing.
6. App shows source, contact details, eligibility, schedule, directions, and a "report outdated" action.

## Important production rule
Do not treat arbitrary scraped web pages as verified facts. Store the source URL, retrieval timestamp, and verification status for every listing. Respect site terms, robots rules, copyright, and API licensing.

## Suggested build phases
Phase 1: search + categories + sample data.
Phase 2: database + real resource ingestion.
Phase 3: location/radius search + map.
Phase 4: organization submissions + moderation.
Phase 5: accounts, saved resources, alerts, analytics, accessibility polish.

## Responsible harvesting
The prototype now includes `sources.json`, `harvester.py`, a source-onboarding checklist, and a conservative harvesting policy. The first enabled connector is Seattle's Emergency Food and Meals open dataset. Seattle Parks and Seattle Public Library are registered as manual-review sources until an authorized machine-readable feed/permission is configured.

## Phone-ready PWA
The project now includes `manifest.json`, `service-worker.js`, `icon.svg`, `app.js`, and `INSTALL.md`.
