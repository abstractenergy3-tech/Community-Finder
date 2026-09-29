# Automated source discovery

Community Finder can now discover potential community-resource sources instead of requiring every source URL to be entered manually.

## What happens automatically

1. A scheduled GitHub Actions job searches for source candidates for each configured city.
2. Candidates are fetched conservatively with a small response limit and a descriptive User-Agent.
3. The verifier checks for:
   - machine-readable/API/feed signals
   - explicit reuse/license/open-data signals
   - government-domain signals
   - robots.txt blocking
   - obvious sensitive-data signals
4. Each candidate receives a score and a decision:
   - `auto_approved` — only when strong machine-readable + explicit reuse signals are present and safety checks pass.
   - `needs_review` — anything ambiguous.
5. Results are stored in `source_candidates` and a JSON artifact is retained for inspection.

## Important legal/safety boundary

Public visibility is **not** treated as permission to scrape. The automation is intentionally conservative. A source without clear reuse/automation evidence remains in `needs_review` even if the page is technically accessible.

The verifier is an engineering safety filter, not legal advice. Production source approval should still follow the project's source policy and any publisher-specific terms.

## Search provider

The discovery job supports either:

- Bing Web Search API: `BING_SEARCH_API_KEY`
- Google Programmable Search: `GOOGLE_SEARCH_API_KEY` + `GOOGLE_SEARCH_ENGINE_ID`

These are stored as GitHub Actions secrets, never in the app or repository.

Without a search-provider secret, the normal harvesting pipeline can still run known approved sources, but new-source discovery will not produce candidates.

## Scaling to new cities

Add a city object and several targeted queries to `discovery_config.json`. The same verifier and database workflow is reused; individual resources do not need to be entered manually.

GitHub Actions supports scheduled workflows and manual runs. urlGitHub Actions workflow documentationhttps://docs.github.com/en/actions/concepts/workflows-and-actions/workflows
