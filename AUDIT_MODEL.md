# Audit model

Every administrative or organization change should produce an immutable audit event.

Suggested fields:

- id
- actor_user_id
- actor_role
- action
- resource_id
- organization_id
- previous_value
- new_value
- reason
- created_at
- source_ip / security metadata where legally appropriate

Examples:
- resource.created
- resource.updated
- resource.verified
- resource.unverified
- resource.deactivated
- claim.submitted
- claim.approved
- claim.rejected
- source.enabled
- source.disabled

Production administrators should never silently edit or delete the history of a listing.
