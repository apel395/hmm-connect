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


## Business dimensions and legacy spreadsheets

Project Catering (Business Unit 002): the Location is the catering site/project
(e.g. PHM = 012, Zamped = 003), while the operational Department is
Operasional = 01. Hotel (Business Unit 001): select the Hotel Location = 009
(the physical premises may be in Pekanbaru), and select the appropriate hotel
line Department (Front Office, House Keeping, etc.). Pekanbaru = 002 belongs
to Project Catering, so it is not a substitute for Hotel Location.

The code columns accept either the exact master code or an unambiguous, exact
master name (case-insensitively); no fuzzy guesses are made. Some previously
distributed spreadsheets have Location/line Department values reversed
(e.g. Location=Operasional, line Department=PHM). On new validation, the worker
corrects that legacy inversion **only** if both original lookups fail, the
reversed values uniquely identify active masters, and their Business Unit
associations match the explicitly selected Business Unit. The corrected
dimensions and a warning appear in the preview. Raw spreadsheet values are
preserved in the import audit records. Any other unknown or conflicting value
remains a validation error. Existing validated batches are not automatically
rerun; create a new batch to revalidate an old file.
