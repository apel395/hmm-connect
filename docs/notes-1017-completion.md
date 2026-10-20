# 10-17 purchasing and master-data follow-up

## Purchasing age policy

The EC2 daily task moves unfinished, unlinked POs older than **six calendar months** to trash. It permanently removes unfinished, unlinked PRs older than **three calendar months**, including their items and approval requests. The strict cutoff excludes the boundary day. Completed documents and documents with source/accounting dependencies remain protected. A linked PR is retained even when its PO is archived. No receipt, invoice, stock, AP, journal, GL, tax or opening balance is deleted by this task.

Preview is read-only. Apply locks each candidate, repeats dependency checks and records the number, previous status and approval evidence in the audit trail. Repeated runs do not repeat changes. The normal PO/PR lists hide archived records. Open **Documents / Trash** on the PO page to view or restore an archived PO. Age-expired approvals are cancelled; restoration returns the PO to DRAFT for fresh approval, retaining the old approval snapshot in the audit. Restoration checks that another PO or direct Market List receiving has not already consumed its source quantities. A restored PO gets a new six-month retention window from restoration; its original order date is unchanged.

```bash
/opt/hmm-connect/.venv/bin/python scripts/run_purchasing_retention.py
/opt/hmm-connect/.venv/bin/python scripts/run_purchasing_retention.py --apply
```

To schedule the task, use a persistent checkout (not `/tmp`) with the production `.env` linked, then run:

```bash
sudo /opt/hmm-connect/.venv/bin/python scripts/install_purchasing_retention.py --app-dir "$PWD"
systemctl list-timers mmh-purchasing-retention.timer
```

The timer runs daily at 03:00 Asia/Jakarta. The job runs as the checkout's owner. `journalctl -u mmh-purchasing-retention.service` contains each run's summary and protected documents. To stop future cleanup: `sudo systemctl disable --now mmh-purchasing-retention.timer`.

## Hotel outlets

Run migration `20261020_department_outlets`. In **Master Data → Departments**, choose the Hotel unit and an optional parent department. An outlet remains a distinct department ID usable in existing journal, purchasing, budget, stock and report dimensions. It inherits the parent's configured location availability. Only one hierarchy level is supported; cycles, cross-unit parents and deactivating a parent with active children are rejected. Catering remains separate by location.

Report labels show `Food and Beverage / Restaurant`, for example. Outlets use their parent's P&L layout and summary grouping while retaining separate detail sheets. Each journal amount is counted once: the parent department's own activity and each outlet's activity stay separate. Selecting a parent department alone reads its own transactions; the Hotel total includes all outlets. No existing department or outlet is invented, no historical department IDs are reassigned, and no journal changes are made. Before migration, existing department reads and reports remain available; saving an outlet asks for the migration.

## Utensils and selling items

Named dining utensils/cutlery and explicitly classified chinaware, silverware or glassware cannot create a new fixed-asset registration. Use MATERIAL and choose STOCK or DIRECT_USE according to actual usage. The guard applies to Item Master saves, automatic asset intake and manual asset-item intake. Linen is unaffected. Existing valued assets require a separate reviewed correction; the app does not silently remove their accounting.

SELL items use NON_STOCK. Numeric groups determine their canonical names: 5 FOOD, 6 BEVERAGE, 7 SERVICE, 8 ROOM. Room remains Hotel-only; SELL has no subgroup. The existing guarded `scripts/renumber_sell_items_1017.py` remains the command for legacy code repair.

```bash
/opt/hmm-connect/.venv/bin/python scripts/check_1017_master_data.py
```

This read-only inspection lists remaining Sell Item/code issues, utensil asset registrations with their values and stock, and configured outlets. Production classification changes need that evidence; unknown existing data is not treated as already corrected.

Names, timestamps and approved signature assets already use the authenticated purchasing print payload. General Cashier and Petty Cash Usage retain their existing auditable draft/post flows.
