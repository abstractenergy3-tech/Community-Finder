# Live-data flow

Approved source
   ↓
Source adapter
   ↓
Permission + robots gate
   ↓
Fetcher (rate/size limited)
   ↓
Raw source record
   ↓
Normalizer
   ↓
Duplicate detection
   ↓
Freshness check
   ↓
Verification status
   ↓
Database
   ↓
Location/radius search
   ↓
Mobile app

## Production states

- `source-derived`: imported from an approved source but not individually verified.
- `verified`: checked by an administrator or trusted organization.
- `community-submitted`: submitted by a user/organization and awaiting verification.
- `stale`: not refreshed within the source-specific freshness window.
- `inactive`: explicitly closed/removed.

## Ranking

Initial ranking should be transparent:
1. Within requested radius
2. Text/category relevance
3. Distance
4. Freshness
5. Verification status

Do not hide source provenance. Users should be able to see where a listing came from.
