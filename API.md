# API contract

GET /resources?lat={lat}&lng={lng}&radius={miles}&category={category}&q={query}

Returns:
{
  "results": [
    {
      "id": "...",
      "title": "...",
      "category": "Food",
      "description": "...",
      "distance_miles": 1.2,
      "address": "...",
      "website": "...",
      "phone": "...",
      "last_verified_at": "...",
      "verification_status": "verified"
    }
  ]
}

POST /reports
Body:
{
  "resource_id": "...",
  "reason": "closed|wrong_info|duplicate|other",
  "details": "..."
}

POST /organizations/submissions
Creates an organization/resource submission for admin review.

Security:
- Require authenticated users for reports/saves.
- Validate and rate-limit submissions.
- Never expose private admin fields.
- Keep audit logs for edits to listings.
