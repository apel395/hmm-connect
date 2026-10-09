# Client-specific PHR AR invoice

Open an AR invoice and choose **Client invoice layout** (gear). Select **PHR catering invoice** and save. This applies to that customer only. Confirm the billing address and configure the MMH letterhead, attention, default contract, payment instructions and authorized signatory.

Choose **Invoice service details** (document icon) to enter that invoice's service period, registration numbers, descriptions, service amounts, tax label/amount and amount in words. Contract number/date can override customer defaults. Saved details belong to the individual invoice.

Service amounts plus explicit tax must equal the existing AR invoice amount. Print becomes available after matching details are saved. No tax rate is assumed. Print settings do not change AR, tax postings, receipts, GL or journals.

The reference format is the first invoice page of `MMH-MNS.186.VI.2026.pdf`: company letterhead, bill-to/contract section, numbered service table, subtotal/tax/grand total, amount in words, bank instructions and authorization space. Signatures, stamps and supporting documents are not copied from the sample.

Storage uses the existing `ar_invoice_layouts.configuration` JSON. No migration or EC2 command is required. Manage access is required to edit; legacy AR retains the consolidated finance restriction.

Backend validation: `pytest tests/test_phr_invoice_print.py`. Frontend validation: `node scripts/test-phr-invoice.mjs` and `npm run build`.
