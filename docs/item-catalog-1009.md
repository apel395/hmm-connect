# Hotel and Catering Item Master delivery

Existing Item Master records remain in the CATERING catalog. HOTEL starts empty;
new registrations from the Hotel Items menu carry HOTEL. Catalog choice is
independent from BUY/SELL, group/subgroup and work-location permissions. Item
IDs and code allocation remain shared so source links stay valid.

BUY reference costs offer LAST_PURCHASE, AVERAGE_PURCHASE or MANUAL. Latest and
quantity-weighted average costs use posted receiving since 2026-01-01, in the
purchase unit and excluding tax. Assigned-location users see only price history
in their assigned location. A missing history falls back to the master cost.
PO and direct receiving prefill the reference; the document price remains
editable. This feature does not rewrite stock costs or accounting.

Hotel Direct Use consuming lines require an explicit expense destination and a
consuming department. Receiving snapshots the expense account on each line.
Its journal debits that expense with the receipt's location/department and
credits AP Suspense. Supplier invoicing clears suspense to AP and retains the
selected expense in its line snapshot. Fixed assets keep capitalization routing.

Each RR has one consuming department. Purchases for different departments use
separate RRs, which can share expense accounts. P&L measures both the account
(nature of expense) and department (who consumed it). Inventory and fixed asset
accounts cannot be selected as consumption expenses.

Existing approved COA seed candidates include:

| Usage | Account |
| --- | --- |
| F&B food cost | 500-100-100 Beban Pokok Makanan |
| F&B drink cost | 500-100-102 Beban Pokok Minuman |
| Staff dining | 600-100-107 Makan Karyawan |
| Stationery | 700-500-103 Alat Tulis Kantor (ATK) |
| Cleaning | 700-500-104 Kebersihan dan Pest Control |
| Operating / guest supplies | 700-500-119 Alat & Perlengkapan |
| Laundry | 700-500-123 Laundry dan Dry Cleaning |
| Equipment repairs | 700-500-106 Perbaikan Peralatan Operasional |
| Building repairs | 700-500-124 Perbaikan Gedung |
| Marketing | 700-500-120 Iklan,Promosi dan Marketing |

These are candidates from the repository seed, not an assertion that every code
is active in the live DB. Guest supplies currently has no separately named
posting account in that seed; 700-500-119 is broad. Account choice remains
explicit, not inferred from an item name or department name.

Reference: HFTP USALI supports separate departmental schedules and expense
nature classifications. Its guest-supplies guidance includes toiletries and
complimentary water/coffee in rooms. Food or drink for sale is F&B cost rather
than automatically guest supplies:
https://www.hftp.org/downloads/documents/usali/resources/usali_faqs.pdf
https://www.hftp.org/downloads/documents/usali/resources/usali11_resources_collection.pdf

New live receiving approval defaults to Store and PM/Camp Boss, with two distinct
people. Existing in-flight approval snapshots stay intact. Historical entry
retains Draft → Post. Stock Opname requires an explicit consuming department.

## Rollout

Run the additive migration from the feature branch before merging it into
backend (which deploys Lambda). Then merge backend and UI. EC2's export worker
must run the updated worker for catalog-specific product exports.

Migration: 20261009_item_receiving, after 20261008_asset_item_master.
No balances, stock, tax flags or historical transactions are rewritten.

Read-only checks:

```
.venv/bin/python scripts/check_item_catalog_1009.py
.venv/bin/python scripts/inspect_hotel_direct_use_accounts.py
```
