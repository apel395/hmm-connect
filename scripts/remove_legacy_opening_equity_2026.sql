-- One-time removal of the two legacy auto-generated 2026 opening equity lines.
-- Leaves the other lines in journals 1242 and 1318 POSTED as requested.
-- This intentionally makes the posted opening ledger out of balance.
BEGIN;
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout = '30s';
SELECT pg_advisory_xact_lock(20260929, 299);
LOCK TABLE opening_balances, journal_entries, journal_lines, general_ledger
    IN SHARE ROW EXCLUSIVE MODE;

DO $$
DECLARE
    before_difference numeric(20, 2);
    after_difference numeric(20, 2);
    affected integer;
BEGIN
    IF (SELECT count(*) FROM chart_of_accounts
        WHERE id = 299 AND account_number = '300-100-100'
          AND account_name = 'Modal Awal Disetor') <> 1 THEN
        RAISE EXCEPTION 'Account 299 does not match Modal Awal Disetor';
    END IF;

    IF (SELECT count(*) FROM journal_entries
        WHERE id IN (1242, 1318) AND status = 'POSTED'
          AND reference_type = 'OPENING_BALANCE'
          AND reference_id = 2026
          AND posting_date = DATE '2026-01-01') <> 2 THEN
        RAISE EXCEPTION 'Opening journals changed; no deletion made';
    END IF;

    IF (SELECT count(*) FROM opening_balances WHERE account_id = 299) <> 2
       OR (SELECT count(*) FROM opening_balances o
           JOIN (VALUES (39, 1242, 13085228194.00::numeric),
                        (47, 1318, 870279803.00::numeric))
                AS expected(id, journal_id, amount)
             ON o.id = expected.id
            AND o.journal_entry_id = expected.journal_id
            AND o.amount = expected.amount
           WHERE o.account_id = 299 AND o.fiscal_year = 2026
             AND o.location_id = 1 AND o.balance_type = 'CREDIT'
             AND o.description = 'Opening Balance Contra') <> 2 THEN
        RAISE EXCEPTION 'Opening equity records changed; no deletion made';
    END IF;

    IF (SELECT count(*) FROM journal_lines WHERE account_id = 299) <> 2
       OR (SELECT count(*) FROM journal_lines l
           JOIN (VALUES (1242, 13085228194.00::numeric),
                        (1318, 870279803.00::numeric))
                AS expected(journal_id, amount)
             ON l.journal_entry_id = expected.journal_id
            AND l.credit = expected.amount
           WHERE l.account_id = 299 AND l.debit = 0
             AND l.description = 'Opening Balance Contra') <> 2 THEN
        RAISE EXCEPTION 'Journal equity lines changed; no deletion made';
    END IF;

    IF (SELECT count(*) FROM general_ledger WHERE account_id = 299) <> 2
       OR (SELECT count(*) FROM general_ledger g
           JOIN journal_entries j ON j.journal_number = g.reference_number
           JOIN (VALUES (1242, 13085228194.00::numeric),
                        (1318, 870279803.00::numeric))
                AS expected(journal_id, amount)
             ON j.id = expected.journal_id AND g.credit = expected.amount
           WHERE g.account_id = 299 AND g.debit = 0
             AND g.reference_type = 'OPENING_BALANCE'
             AND g.reference_id = 2026
             AND g.posting_date = DATE '2026-01-01') <> 2 THEN
        RAISE EXCEPTION 'General Ledger equity rows changed; no deletion made';
    END IF;

    SELECT coalesce(sum(l.debit - l.credit), 0)
      INTO before_difference
      FROM journal_lines l
      JOIN journal_entries j ON j.id = l.journal_entry_id
     WHERE j.status = 'POSTED';

    DELETE FROM general_ledger
     WHERE account_id = 299 AND reference_type = 'OPENING_BALANCE'
       AND reference_id = 2026
       AND reference_number IN (
           SELECT journal_number FROM journal_entries WHERE id IN (1242, 1318)
       );
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 2 THEN RAISE EXCEPTION 'Expected to delete 2 GL rows, got %', affected; END IF;

    DELETE FROM journal_lines
     WHERE account_id = 299 AND journal_entry_id IN (1242, 1318);
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 2 THEN RAISE EXCEPTION 'Expected to delete 2 journal lines, got %', affected; END IF;

    DELETE FROM opening_balances WHERE id IN (39, 47) AND account_id = 299;
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 2 THEN RAISE EXCEPTION 'Expected to delete 2 opening rows, got %', affected; END IF;

    IF EXISTS (SELECT 1 FROM journal_lines WHERE account_id = 299)
       OR EXISTS (SELECT 1 FROM general_ledger WHERE account_id = 299)
       OR EXISTS (SELECT 1 FROM opening_balances WHERE account_id = 299) THEN
        RAISE EXCEPTION 'Residual financial rows remain on account 299';
    END IF;

    IF (SELECT coalesce(sum(debit - credit), 0) FROM journal_lines
        WHERE journal_entry_id = 1242) <> 13085228194.00
       OR (SELECT coalesce(sum(debit - credit), 0) FROM journal_lines
           WHERE journal_entry_id = 1318) <> 870279803.00 THEN
        RAISE EXCEPTION 'Remaining opening journal totals differ from expected';
    END IF;

    SELECT coalesce(sum(l.debit - l.credit), 0)
      INTO after_difference
      FROM journal_lines l
      JOIN journal_entries j ON j.id = l.journal_entry_id
     WHERE j.status = 'POSTED';
    IF after_difference - before_difference <> 13955507997.00 THEN
        RAISE EXCEPTION 'Posted ledger difference did not change by the expected amount';
    END IF;

    RAISE NOTICE 'Removed 2 opening rows, 2 journal lines and 2 GL rows. Posted debit-credit difference moved from % to %.',
        before_difference, after_difference;
END $$;
COMMIT;

SELECT j.id, j.journal_number, j.status,
       sum(l.debit) AS remaining_debit, sum(l.credit) AS remaining_credit,
       sum(l.debit - l.credit) AS difference
  FROM journal_entries j
  JOIN journal_lines l ON l.journal_entry_id = j.id
 WHERE j.id IN (1242, 1318)
 GROUP BY j.id, j.journal_number, j.status
 ORDER BY j.id;
