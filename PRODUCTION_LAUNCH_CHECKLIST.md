# Production launch checklist

## Phase A — create the backend
- [ ] Create a hosted PostgreSQL/Supabase project.
- [ ] Run `supabase/001_bootstrap.sql`.
- [ ] Create authentication for organization/admin accounts.
- [ ] Configure Row Level Security / API authorization.
- [ ] Add server-side API endpoints.
- [ ] Add audit logging.
- [ ] Configure HTTPS and rate limits.

## Phase B — connect data
- [ ] Review every source in `sources.json`.
- [ ] Re-confirm current reuse/automation permission before enabling it.
- [ ] Set source-specific refresh intervals.
- [ ] Run the harvester in a server/CI environment.
- [ ] Upload normalized records through an authenticated server endpoint.
- [ ] Reject or quarantine malformed records.
- [ ] Monitor stale listings and failed harvests.

## Phase C — phone app
- [ ] Host the PWA over HTTPS.
- [ ] Test location permission on Android.
- [ ] Test denied-location fallback.
- [ ] Test offline shell.
- [ ] Test screen-reader navigation.
- [ ] Test low-bandwidth behavior.
- [ ] Add privacy policy and terms before public launch.

## Phase D — operational safety
- [ ] Never publish an unverified source permission.
- [ ] Never put service credentials in frontend JavaScript.
- [ ] Add a source kill switch.
- [ ] Add error alerts for repeated harvest failures.
- [ ] Add stale-data alerts.
- [ ] Keep a human review path for organizations and disputed listings.
