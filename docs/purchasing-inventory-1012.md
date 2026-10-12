# Purchasing and inventory — 12 October 2026

## Receiving and purchasing

Normal receiving takes its date from server submission. Historical Entry retains its selected date under the open-period/backdate policy; pre-2026 receipts remain excluded. Accounting dates follow Asia/Jakarta. PO candidates show estimated delivery dates and remaining items, with date filters. Existing partial-receipt limits and two distinct approvers remain enforced.

An approved Market List can be received directly, without another PO. Supplier selection and source organization remain explicit. Draft/posted direct receipt quantities and non-cancelled PO quantities share ML allocation limits under a source-row lock. PO conversion takes only the remaining ML quantity. A PO cannot precede its source PR request date; same-day creation is allowed.

STOCK and DIRECT_USE retain their actual destination behavior. Direct Use creates no artificial warehouse IN/OUT. Receiving retains its existing draft source-accounting journal for the finance posting workflow; old receipt journals are not automatically posted.

## Inventory

Stock Movement displays Remaining on every row, calculated by item/warehouse from complete history. Visible date/source/search filters do not reset the balance. Source journal date supplies the event date when available; legacy events use their existing receiving/event timestamp. Manual opening quantities remain snapshots, not manufactured transactions.

Stock-age columns are removed from the main list. Estimated FIFO aging retains the existing 30-day fast threshold, slow through six calendar months, and dead older than six calendar months. New purchases do not reset the age of old remaining stock. These are aging estimates, not physical lot records or turnover ratios.

Store Request retains approval and request date. Store Issue adds warehouse issue date and posts stock/journal/GL together. Duplicate posting is refused; backdating follows accounting-period policy.

Stock Opname already requires department. Location users receive blind counts: system quantity, cost and variance are omitted from API and print responses. The interface hides system-copy shortcuts. Review users with unrestricted location access retain those fields.

Approved stock-count shortages debit mapped item COGS/expense and credit inventory; surpluses reverse those sides. Missing mappings/costs or stale quantity/cost snapshots prevent posting. Stock and accounting are transactional. Zero variance creates no journal. Unpost removes only the source GL, returns the same journal to draft, and restores stock; repost reuses it. Later stock activity prevents unsafe reversal.

## Closing, archive and printing

Accounting Periods shows unfinished purchasing documents before close and returns them in the close response. These documents do not automatically block or alter closing balances.

Purchasing Reports includes Unfinished/Archive. Only failed/cancelled documents without downstream evidence can be archived. Restore retains prior status and audit history. No physical deletion is performed.

App print buttons issue tracked copies, with reprint numbers and correction/unpost marks. Preview does not count. Counts are print requests: cancelling the browser print dialog still counts an issued request; native Ctrl+P is outside app tracking. Stock-count print removes Officer and hides system quantities for blind counts. Movement print adds Remaining.

## Release and validation

Migration `20261012_purch_inventory` follows `20261009_item_receiving`, adding nullable ML source links and Store Issue date. No historical stock, tax, journal, GL or opening-balance records are rewritten.

Apply the migration from a reviewed feature worktree using the EC2 .env and .venv BEFORE merging backend, because pushing backend deploys Lambda automatically. Frontend release is main/Vercel. After merge, EC2 can pull and run:

```bash
cd /opt/hmm-connect
git pull --ff-only origin backend
.venv/bin/python scripts/check_purchasing_inventory_1012.py
sudo systemctl restart hmm-connect-export-worker
```

The checker is read-only and reports legacy posted issues with draft journals without repairing them automatically. Finance must inspect source evidence before any repair. Local validation: 287 backend tests, migration graph, frontend build/ESLint, finance checks and inventory print checks.
