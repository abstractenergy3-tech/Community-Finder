# Supabase connection

The PWA is configured with the project's public Supabase URL and publishable key.
The browser reads active resources through Supabase REST and relies on Row Level Security.
Privileged credentials are not included in the app.

The current MVP uses a bounding-box location query. Production should move exact radius calculations and privileged operations to the backend.
