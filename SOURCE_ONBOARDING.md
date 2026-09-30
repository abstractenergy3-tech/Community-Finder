# Source onboarding — conservative and automated

Community Finder uses a two-stage model:

`known source → technical/reuse checks → candidate → auto-approval or review → source registry → scheduled harvest`

## Automatic verification

A source can be auto-enabled only when the verifier has:

- a machine-readable/API/feed signal;
- explicit reuse/open-data/license evidence configured for that source;
- no robots.txt block for the candidate URL;
- no obvious sensitive-data signal; and
- a high-confidence score.

A public webpage by itself is never enough to authorize automatic scraping.

## Review queue

Ambiguous sources become `needs_review` in `source_candidates`. This is intentional: the system can verify technical details without silently deciding that a publisher permits automated reuse.

## Adding a city

Add the city and targeted query labels to `discovery_config.json`, then add specific source records to `known_sources.json`. You do not need to enter individual food banks, programs, or events into the discovery configuration.

## Production credentials

Only these GitHub Actions secrets are required by the upload step:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

The service-role key must never be placed in frontend files or committed to Git.

No Bing or Google search credentials are required by this version.
