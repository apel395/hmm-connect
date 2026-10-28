# PostgreSQL concurrency gate

PR #485 adds a `PostgreSQL journal concurrency` CI job using a disposable PostgreSQL 16 service. It does not use EC2, AWS credentials, production secrets or production data. The normal full backend suite remains a separate job.

The six tests exercise two independent connections with actual row locks:

- Double journal posting: exactly one finalization and one set of GL rows.
- Posting racing period close: one source posting and one closing set.
- Closing racing editing: editing waits, then rejects the closed period.
- Closing racing unposting: unposting waits, then rejects the closed period.
- Double period closing: both requests return the same closing evidence.
- Double payment settlement: one allocation application; no second GL posting.

Each test observes `pg_blocking_pids()` to prove contention before releasing the first transaction. Timeouts fail the test instead of leaving a worker blocked indefinitely. Each test also verifies that the opening balance is unchanged.

Tests require a database named exactly `mmh_journal_concurrency_test`. Each test creates and drops only its own randomly named schema; application/public tables are not used. Without `MMH_PG_TEST_URL`, these tests skip in the normal SQLite suite.

For optional EC2 verification, create a separate empty database and restricted test role, export both `DATABASE_URL` and `MMH_PG_TEST_URL` to that test database, and run:

```bash
.venv/bin/python -m pytest -q tests/test_journal_postgres_concurrency_1028.py -rA
```

Never substitute the production database URL. The disposable CI job is the default check and needs no EC2 setup. Before merge, require both the full backend suite and PostgreSQL concurrency job to be green on the latest PR commit, plus frontend validation/audit. This is focused service-level locking verification, not a production load test or a full staging browser walkthrough.
