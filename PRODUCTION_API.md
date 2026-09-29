# Production API

The browser should not connect directly to PostgreSQL.

Recommended flow:

Phone/PWA -> HTTPS API -> PostgreSQL
                     -> source harvester
                     -> moderation/audit

## Public endpoints

`GET /api/resources?lat=47.6&lng=-122.3&radius=15&q=food&category=Food`

Returns only active, publishable listings.

`GET /api/resources/:id`

Returns one public listing.

`POST /api/reports`

Creates an outdated/inaccurate listing report. Rate-limit this endpoint.

## Authenticated endpoints

Organization users:
- `POST /api/organization/resources`
- `PATCH /api/organization/resources/:id`
- `POST /api/organization/claims`

Admins:
- `GET /api/admin/review`
- `POST /api/admin/submissions/:id/approve`
- `POST /api/admin/submissions/:id/reject`
- `POST /api/admin/sources/:id/enable`
- `POST /api/admin/sources/:id/disable`

## Security rules

- Never expose `SUPABASE_SERVICE_ROLE_KEY` to the browser.
- Public reads should use a narrowly scoped API/RLS policy.
- Validate every submitted field server-side.
- Treat URLs as untrusted input.
- Enforce maximum description/title lengths.
- Rate-limit reports and organization submissions.
- Require authentication for organization/admin mutations.
- Write an audit event for every privileged change.
- Do not store precise device coordinates unless there is a documented need.
- Prefer radius searches around the user's current location rather than retaining location history.

## Deployment variables

```
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
HARVEST_USER_AGENT=
CRON_SECRET=
```

Only the public anon key belongs in a browser build. Service-role and cron secrets stay server-side.
