# Approval print identity follow-up — 21 October 2026

The 10-17 name/time/signature requirement applies to the actual approver. A role
name alone is not evidence that the stored signature belongs to that person.

Document context now supplies the recorded approver's user ID. Existing Batam
signature assets are attached only for an APPROVED step with a decision time,
matching owner name and uniquely matching owner user ID. Case, Unicode width
and whitespace differences are normalized; aliases, initials and partial names
are not matched. Missing identity, duplicate names, other locations and
rejected/pending steps leave the signature space blank. Reused payloads clear
old signature fields before validation. No new signatures or signers are
created and no stored asset image is changed.

Purchasing, Store Request, Stock Opname, payment voucher and finance print pages
share an approval display helper. The displayed name comes from the approver,
never from the image owner. The frontend also suppresses mismatched images so
older API responses cannot substitute another person's name or signature.
Store Request includes its recorded creator and approval timestamps. Shared
print layout keeps signature space and renders date/time in Asia/Jakarta/WIB.
Print counts and correction marks retain their existing tracking rules.

Verification includes backend identity/role/status/location tests, document
context integration, and rendered purchasing/store/count print pages with an
intentionally mismatched asset. The frontend checks run in `npm run test:finance`.

No database migration or production data script is required. Deferred SELL
seeding, Hotel outlet setup, signature uploads and asset activation are not
performed by this patch.
