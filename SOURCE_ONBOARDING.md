# Source onboarding — automated first

Community Finder no longer needs a manual entry for every potential source.

## Automatic path

`city + search queries → discovery → technical/reuse checks → candidate → auto-approval or review → source registry → scheduled harvest`

The discovery service looks for APIs, open-data endpoints, downloadable datasets, RSS/ICS feeds, and similar machine-readable sources.

## Auto-approval rules

A source can be auto-enabled only when the verifier finds:

- a machine-readable/API/feed signal;
- an explicit reuse/open-data/license signal;
- no robots.txt block for the candidate URL;
- no obvious sensitive-data signal; and
- a high-confidence score.

A public webpage by itself is **never** enough to authorize automatic scraping.

## Review queue

Everything else becomes `needs_review` in `source_candidates`. This lets the system discover many possibilities without silently assuming permission.

## Adding a city

Add a city and targeted queries to `discovery_config.json`. You do not add individual food banks, programs, events, etc. The source connector is responsible for discovering those records after a source is approved.

## Production credentials

Keep these only in GitHub Actions Secrets:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- either `BING_SEARCH_API_KEY`, or `GOOGLE_SEARCH_API_KEY` + `GOOGLE_SEARCH_ENGINE_ID`

Never put the service-role key in `app.js`, `supabase-config.js`, or chat.
