# Journal and report delivery — 10-10

No database migration is required.

Journal registers filter by configured business unit (Hotel / Project Catering). A scoped user defaults to and remains restricted to their assigned location. Administrators may switch units and locations. Legacy journals with a missing header business unit use their location's unit for listing. Print registers retain unit, location and supplier filters.

Copy opens an independent manual journal form. It keeps account amounts, per-line department/supplier context and the organization context; the user selects a date and enters a new document number. Saving creates a DRAFT, audits the source journal ID, and does not alter the original or create GL/source-document postings. Opening and system closing journals cannot be copied.

Trial Balance Opening remains the manually recorded preceding-year closing. From/To dates select only movement within the chosen range. Earlier current-year movement is separately displayed as Prior Debit / Prior Credit. Closing includes Opening + prior movement + selected movement. Status and balance checks evaluate the complete closing without hiding the opening imbalance. Screen, print and Excel use the same range. The legacy `/trial-balance/export` URL now delivers XLSX.

P&L can return full statements per configured or historically used department, including inactive departments and unassigned activity, with MTD/YTD actuals and comparisons. Explicit unassigned drilldowns use `department_id=0`; ordinary omitted department means all departments. Department tables appear in print and separate Excel sheets. No costs are distributed automatically and report setup never changes accounting totals.

EC2 read-only validation:

```bash
.venv/bin/python scripts/check_finance_scope_1010.py --from-date 2026-10-01 --to-date 2026-10-31 --location-id 8
```
