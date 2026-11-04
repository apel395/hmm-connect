# Read-only Catering/POS access comparison

Use `PYTHONPATH=. .venv/bin/python scripts/check_pos_access_1104.py --user-id ID1 --user-id ID2`
to compare the actual accounts involved in #509. Choose explicit existing IDs.
The command prints no passwords, tokens or financial values. It checks account
activity, canonical administrator role, POS permission grants, location/unit/
department assignments, available locations and eligible menu counts.

It reuses existing scoped POS options/menu readers; PostgreSQL is explicitly set
to READ ONLY and the session is rolled back after inspection. No role, user,
permission, master item, stock or financial record is changed.

Regression tests cover two SYSTEM_ADMINISTRATOR profiles with different assigned
locations (same menus), custom Admin roles with/without explicit POS permission,
and a Hotel-scoped account correctly lacking Catering visibility.

This is diagnosis, not a production access repair. Account labels do not authorize
superuser access. Do not close #509 until the affected accounts are compared.
No database migration is required.
