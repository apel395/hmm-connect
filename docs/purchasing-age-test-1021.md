# Purchasing age demonstration

`scripts/test_purchasing_age_documents.py` creates nine independent, clearly
numbered DRAFT documents: PR, PO and ML at ages 7, 4 and 2 calendar months.
It reuses existing active suppliers, organization and suitable BUY items; PR/PO
use a non-market item and ML uses an eligible market item. It creates no item
masters, approvals, receiving, stock, invoices, AP, journals or openings.
Audit records identify a system test batch; no real staff member is impersonated.

For `--as-of 2026-10-21`, the source dates are March 21, June 21 and August 21.
The batch is `DUMMY-AGE-20261021-L8` for Hotel location 8.

| Document | 7 months | 4 months | 2 months |
|---|---|---|---|
| PR | Deleted | Deleted | Kept |
| PO | Trash | Kept | Kept |
| ML | Kept | Kept | Kept |

ML has no age-based cleanup policy. The PR/PO policy is unchanged. The normal
03:00 daily cleanup will also handle eligible dummy PR/PO documents. To inspect
immediately, run this script's targeted exercise rather than global cleanup:

```bash
.venv/bin/python scripts/test_purchasing_age_documents.py --as-of 2026-10-21 --location-id 8
.venv/bin/python scripts/test_purchasing_age_documents.py --as-of 2026-10-21 --location-id 8 --apply
.venv/bin/python scripts/test_purchasing_age_documents.py --action inspect --as-of 2026-10-21 --location-id 8
.venv/bin/python scripts/test_purchasing_age_documents.py --action exercise --as-of 2026-10-21 --location-id 8
.venv/bin/python scripts/test_purchasing_age_documents.py --action exercise --as-of 2026-10-21 --location-id 8 --apply
```

Creation and exercise preview roll back by default; `--apply` commits. Exercise
passes only IDs verified against the batch's original audit marker, document
number, date, location, source type and notes to the ordinary retention service.
Other real purchasing documents are outside this test action. Original source
dependency protection still applies. The test uses the same advisory lock as
the scheduled retention worker. It will not create a 2025 fixture or future
cleanup date. Reruns preserve existing fixtures and do not recreate deleted PRs.

Open PR/PO/ML and search `DUMMY-AGE-20261021-L8` to inspect them. After exercising,
open Purchase Order Trash for the 7-month PO. The two deleted PR numbers remain
in the audit log and the test result, rather than in the active PR list.
