# Bulk journal template

The template follows Create Journal Entry: Posting Date, Document Number,
Description, Business Unit, Work Location, Line Department, Account, Line Description,
Debit and Credit. Select organization and account codes from the workbook lists.
Business Unit can be inferred from Work Location; Department is optional and belongs to each account line. Blank line departments stay unassigned; they do not inherit the preceding department. Older templates with department_code retain their original header-default behavior.

Document Number identifies one journal. Repeat it on separated lines belonging
to that journal. Blank document and header cells continue the preceding journal.
Use a different document number to start another journal. A file with no document
numbers is one journal, with a generated import document number. ERP generates
its own official journal number in every case.

Debit and credit are validated per whole document, never as adjacent row pairs.
No balancing line is created automatically. Existing group-based templates remain
readable. New templates and correction exports do not require journal_group.
Corrections preserve optional supplier/reference metadata found in older files.

API changes deploy through backend. On EC2, update the export/import worker code
with `git pull --ff-only origin backend` and restart
`hmm-connect-export-worker`. No database migration is needed.
