# Install Community Finder on a phone

## Easiest route: install the PWA
1. Put this folder on a web host that serves HTTPS.
2. Open the site in Chrome/Safari on the phone.
3. Use the browser's **Add to Home Screen / Install app** option.
4. The app shell and cached pages can continue working when connectivity is poor.

> A service worker generally requires HTTPS (localhost is the main development exception).

## Location privacy
Community Finder only requests browser location after the user taps **Use my location**. The browser controls the permission. The prototype does not create a user account or store the device coordinates on a server by itself.

## Production architecture
- Static PWA frontend
- Authenticated API
- PostgreSQL database using `schema.sql`
- Scheduled source harvesters
- Admin moderation
- Organization submission/claim workflow
- Audit events
- Rate limits and source-specific caching

Do not expose `app_api.py` directly to the public internet. Put production authentication, authorization, validation, rate limiting, logging, and HTTPS in front of the API.
