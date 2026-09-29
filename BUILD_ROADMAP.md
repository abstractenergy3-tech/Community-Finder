# Build roadmap

## Milestone 1 — clickable/local prototype
Done in this package:
- Mobile UI
- Search
- Filters
- Location permission
- Sample listings

## Milestone 2 — real backend
- Create Supabase project
- Run schema.sql
- Add API endpoints
- Connect app to database
- Add admin authentication

## Milestone 3 — real local data
Start with 2–3 trustworthy source types:
- Government/open-data feeds
- Community organization directories that permit reuse
- Direct organization submissions

For every record store source_url and last_verified_at.

## Milestone 4 — geographic discovery
- Convert ZIP/address to coordinates
- Radius query
- Map/list view
- Distance sorting

## Milestone 5 — trust and moderation
- Verification queue
- Report outdated listing
- Duplicate detection
- Automatic freshness reminders
- Organization verification

## Milestone 6 — app-store release
- App icon and branding
- Accessibility audit
- Privacy policy
- Terms
- Crash/error reporting
- Android build
- iOS build if desired
- Store listings and screenshots

## Definition of done for v1
A user can enter a location, find relevant listings, understand what each listing provides, contact the provider, and report inaccurate information.

## Current implementation milestone
The package now includes a local ingestion pipeline, deduplication/freshness logic, radius search, and a small API endpoint for the prototype. This lets the UI consume harvested records instead of being permanently tied to sample data.

## Next production milestone
- Add authenticated organization submission/claim workflow.
- Add admin moderation dashboard.
- Add source registry UI.
- Add map provider and geocoding.
- Add scheduled jobs for enabled sources.
- Add automated stale-source alerts.

## Organization/admin prototype
The package now includes `admin.html`, `organization.html`, and an audit model. These are UI prototypes only; production requires authentication, authorization, server-side validation, database persistence, and audit logging.

## Hosted backend milestone
The repository now contains a PostgreSQL/Supabase-compatible bootstrap, production API contract,
server-side harvest upload path, scheduled GitHub Actions workflow, environment template, and launch checklist.
Actual cloud connection still requires the owner's hosted database/project credentials.
