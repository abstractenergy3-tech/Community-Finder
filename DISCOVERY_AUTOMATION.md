# Automated source discovery — no external search APIs

Community Finder can verify a curated set of known public data sources without requiring Bing or Google search credentials.

## What happens automatically

1. GitHub Actions runs the discovery verifier on a schedule or manual dispatch.
2. `known_sources.json` supplies only sources that the project has intentionally selected for verification.
3. Each source is fetched conservatively with a descriptive User-Agent, a timeout, and a response-size limit.
4. The verifier checks:
   - machine-readable/API/feed signals;
   - reuse/license signals from the source or its explicitly configured evidence URL;
   - government-domain signals;
   - robots.txt blocking; and
   - obvious sensitive/personal-data signals.
5. Candidates receive a score and a decision:
   - `auto_approved` — only when strong technical and reuse evidence is present and safety checks pass;
   - `needs_review` — anything ambiguous.
6. Results are uploaded to `source_candidates`; only high-confidence candidates may be added to `source_registry` by the upload step.

## Important legal and safety boundary

Public visibility is **not** treated as permission to scrape. The verifier is an engineering safety filter, not legal advice. A source remains `needs_review` when the project does not have clear evidence that automated reuse is allowed.

Current publisher terms, dataset-specific licensing, API rules, and privacy restrictions still control production approval. The project should not ingest personal or sensitive information merely because it is publicly reachable.

## No Bing or Google credentials required

This version deliberately does **not** call Bing Web Search or Google Programmable Search APIs. There are no `BING_SEARCH_API_KEY`, `GOOGLE_SEARCH_API_KEY`, or `GOOGLE_SEARCH_ENGINE_ID` requirements.

New sources are added to `known_sources.json` only after the project has identified a specific source and decided it is appropriate to verify. This keeps discovery conservative and avoids silently turning arbitrary web pages into scraping targets.

## Scaling to new cities

Add a city object to `discovery_config.json`, then add intentionally selected source records to `known_sources.json`. Each source can be associated with one or more city queries.

The discovery verifier is reusable across cities, but it does not assume that every public website permits automated collection.
