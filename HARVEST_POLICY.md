# Responsible harvesting policy

## Automatic sources
A source may be automatically fetched only when all of these are true:

1. There is an API, downloadable dataset, or explicitly authorized feed.
2. The source's reuse/access terms have been reviewed.
3. `allowed_automation` is true in `sources.json`.
4. The request passes the source's robots policy when applicable.
5. The harvester obeys a conservative refresh interval.
6. Responses are cached and size-limited.
7. The source URL and collection time are stored with every record.

## Websites without an authorized feed
Do not automatically scrape them merely because the information is publicly visible.

Instead:
- Link to the source.
- Ask the publisher for permission/feed access.
- Use an official RSS/iCalendar/API feed if provided.
- Add the source only after its reuse terms are reviewed.

## Copyright
Prefer facts and structured data over copying prose. Store short factual fields needed for discovery and link users to the original source for full details. Do not copy articles, images, or large blocks of text.

## Personal information
Do not ingest individual people's personal data. Resource listings should represent organizations, programs, places, and public event information.

## Reliability
Every record carries:
- source
- source URL
- collection timestamp
- source hash
- verification status

Expired or repeatedly failing sources should automatically be marked stale rather than silently presented as current.

## Rate limits
Production implementation should use:
- per-source minimum intervals
- exponential backoff
- response caching
- retry caps
- a global concurrency limit
- a manual kill switch
