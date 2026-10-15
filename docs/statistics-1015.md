# Statistical accounts and operational Actual/Budget

Header `900 — Statistik` has account type `STATISTIC`. Create detail metrics as `900-*` with a statistical parent in Chart of Accounts. Financial posting is disabled for every statistical account; use the Statistics menu for operational quantities. Room nights, guests and portions must use separate accounts and units.

Statistics are monthly records by location and optional department. Blank means not entered; zero is an entered value. Actual and Budget are stored separately from financial budget amounts, opening balances, journals and GL. No financial balancing or journal is generated. The first saved unit applies to all subsequent records of that metric. Updates carry a version and reject stale edits. Location scope is enforced on reads and writes; view/manage use existing finance permissions. Saves produce activity audit records.

## Rollout

1. Deploy the Statistic account-type compatibility change first (no schema change). Existing COA APIs must accept STATISTIC before the migration inserts 900.
2. On EC2, fetch `statistics-1015-backend` into an isolated worktree, link `/opt/hmm-connect/.env`, and use `/opt/hmm-connect/.venv/bin/alembic upgrade 20261015_statistics`.
3. Run `scripts/check_statistics_1015.py`. It reads only schema, migration, header and record count.
4. After migration evidence, merge the Actual/Budget backend and Statistics UI branches. Backend push deploys Lambda; main deploys Vercel.

The migration adds one empty table and its indexes plus header 900. It never seeds quantities, changes operational documents or adjusts financial balances. If 900 already has a financial type, migration stops for review.
