# Client-specific PHR AR invoice

Open an AR invoice and choose **Client invoice layout** (gear). Select **PHR catering invoice** and save. This applies to that customer only. Confirm the billing address and configure the MMH letterhead, attention, default contract, payment instructions and authorized signatory.

Choose **Invoice service details** (document icon) to enter that invoice's service period, registration numbers, descriptions, service amounts, tax label/amount and amount in words. Contract number/date can override customer defaults. Saved details belong to the individual invoice.

Service amounts plus explicit tax must equal the existing AR invoice amount. Print becomes available after matching details are saved. No tax rate is assumed. Print settings do not change AR, tax postings, receipts, GL or journals.

The reference format is the first invoice page of `MMH-MNS.186.VI.2026.pdf`: company letterhead, bill-to/contract section, numbered service table, subtotal/tax/grand total, amount in words, bank instructions and authorization space. Signatures, stamps and supporting documents are not copied from the sample.

Storage uses the existing `ar_invoice_layouts.configuration` JSON. No migration or EC2 command is required. Manage access is required to edit; legacy AR retains the consolidated finance restriction.

Backend validation: `pytest tests/test_phr_invoice_print.py`. Frontend validation: `node scripts/test-phr-invoice.mjs` and `npm run build`.


## November 3 print-layout alignment

PHR customers without an explicit saved template now default to the PHR layout
(read-only detection by PHR code/name or Pertamina Hulu Rokan name). Explicit
Standard/PHR selections and all saved client and per-invoice settings are kept.

Both AR Invoice and POS invoice print use the same PHR component and authorized
AR document. The POS print endpoint scopes both the sale and receivable, excludes
receipt-history details, and does not write any invoice, tax, payment or GL data.
Normal POS receipts and non-PHR invoice layouts are unchanged.

The first reference page is reproduced as a Letter portrait invoice: separate
rounded letterhead/body frames, bill-to and contract metadata, numbered Reg No./
Service/Amount table, total/tax/grand total/Total be Paid, Said, bank instructions
and blank authorization space. Numeric formatting follows the supplied invoice
(comma thousands, two decimal places). Terbilang is derived from the actual
invoice amount only when no saved wording exists. Existing bank, contract and
signatory settings remain authoritative; historical sample data, signatures,
stamps and meterai are never populated into real invoices.

No database migration is required. Backend regression tests cover template
defaults, preserved financial identity/totals, POS/AR parity and location access.
Frontend rendering tests cover the reference values, escaping, terbilang,
print-readiness, POS fallback and shared PHR rendering. Two-line and long invoice
fixtures have been rendered and visually checked for print layout/pagination.
