-- One-time cleanup of the two legacy 2026 opening journals after the
-- opening-snapshot backend is deployed. OpeningBalance rows remain unchanged
-- except their obsolete journal link is set to NULL.
--
-- Review transaction output first. This file deliberately ends in ROLLBACK.
-- Change the final ROLLBACK to COMMIT only after verifying the target rows
-- and the matching GL lines on the production database.
BEGIN;

DO $$
DECLARE
    target_count integer;
    linked_count integer;
    journal_line_count integer;
    ledger_line_count integer;
BEGIN
    SELECT count(*) INTO target_count
    FROM journal_entries
    WHERE id IN (1242, 1318)
      AND status = 'POSTED'
      AND reference_type = 'OPENING_BALANCE'
      AND reference_id = 2026
      AND posting_date = DATE '2026-01-01';

    IF target_count <> 2 THEN
        RAISE EXCEPTION 'Expected the two verified 2026 opening journals, found %', target_count;
    END IF;

    SELECT count(*) INTO linked_count FROM opening_balances
    WHERE journal_entry_id IN (1242, 1318) AND fiscal_year = 2026;
    IF linked_count = 0 OR EXISTS (
        SELECT 1 FROM opening_balances
        WHERE journal_entry_id IN (1242, 1318) AND fiscal_year <> 2026
    ) THEN
        RAISE EXCEPTION 'OpeningBalance links do not match the 2026 snapshot';
    END IF;

    SELECT count(*) INTO journal_line_count FROM journal_lines
    WHERE journal_entry_id IN (1242, 1318);
    SELECT count(*) INTO ledger_line_count
    FROM general_ledger gl
    JOIN journal_entries j ON j.document_number = gl.document_number
    WHERE j.id IN (1242, 1318)
      AND gl.reference_type = 'OPENING_BALANCE'
      AND gl.reference_id = 2026
      AND gl.reference_number = j.journal_number;

    IF journal_line_count = 0 OR journal_line_count <> ledger_line_count THEN
        RAISE EXCEPTION 'Journal/GL row counts differ: % / %', journal_line_count, ledger_line_count;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM journal_entries j
        JOIN general_ledger gl
          ON gl.document_number = j.document_number
          OR gl.reference_number = j.journal_number
        WHERE j.id IN (1242, 1318)
          AND (gl.reference_type IS DISTINCT FROM 'OPENING_BALANCE'
               OR gl.reference_id IS DISTINCT FROM 2026)
    ) THEN
        RAISE EXCEPTION 'Unexpected GL references to a legacy opening journal';
    END IF;

    RAISE NOTICE 'Verified: % journals, % opening values, % journal lines, % GL lines',
        target_count, linked_count, journal_line_count, ledger_line_count;
END $$;

SELECT j.id, j.journal_number, j.document_number,
       (SELECT count(*) FROM opening_balances ob WHERE ob.journal_entry_id = j.id) AS opening_values,
       (SELECT count(*) FROM journal_lines l WHERE l.journal_entry_id = j.id) AS journal_lines
FROM journal_entries j WHERE j.id IN (1242, 1318) ORDER BY j.id;

UPDATE opening_balances SET journal_entry_id = NULL
WHERE journal_entry_id IN (1242, 1318) AND fiscal_year = 2026;

DELETE FROM general_ledger gl
USING journal_entries j
WHERE j.id IN (1242, 1318)
  AND gl.document_number = j.document_number
  AND gl.reference_number = j.journal_number
  AND gl.reference_type = 'OPENING_BALANCE'
  AND gl.reference_id = 2026;

DELETE FROM journal_lines WHERE journal_entry_id IN (1242, 1318);
DELETE FROM journal_entries WHERE id IN (1242, 1318);

SELECT count(*) AS retained_opening_values FROM opening_balances WHERE fiscal_year = 2026;
SELECT count(*) AS remaining_legacy_journals FROM journal_entries WHERE id IN (1242, 1318);
ROLLBACK;
