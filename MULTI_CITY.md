# Multi-city architecture

Cities are configuration, not separate applications.

To add a city:
1. Add a city entry to `cities.json`.
2. Add approved sources to `sources.json`.
3. Map each source to a category/data adapter.
4. Confirm reuse/automation terms.
5. Run the source onboarding checklist.
6. Set geographic center/default radius.
7. Test normalization and duplicate detection.
8. Enable the city.

## Why this matters

The same app can support:
- Seattle
- Portland
- San Francisco
- New York
- Any other city with suitable public/authorized data

The user does not need to know which government agency or nonprofit maintains a resource. The app presents the information in one consistent interface while preserving the original source.

## Organization participation

Organizations should eventually be able to:
- submit a resource
- claim an existing listing
- update hours/contact details
- mark a program temporarily unavailable
- provide an official feed
- see when the listing was last checked

All organization edits should enter an audit trail and, depending on risk, an approval queue.
