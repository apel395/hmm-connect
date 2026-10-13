# Owner overview and multi-department journals

Executive View is a dedicated sidebar page at `/executive-view`. It uses the
existing scoped financial reporting endpoints and `finance.view` permission.
It displays performance and position headlines, budget and prior-period
comparisons and links to financial reports. No COA detail, transaction tables
or document entry actions are presented. Missing comparisons/budgets remain
unavailable; zero revenue does not produce a fabricated margin.

References: Oracle Hospitality OPERA Reporting and Analytics dashboards
https://docs.oracle.com/en/industries/hospitality/opera-reporting-analytics/ugrna/c_dashboards.htm
and Microsoft Business Central Finance app KPI guidance
https://learn.microsoft.com/en-us/dynamics365/business-central/finance-powerbi-kpis

One journal consists of one header/register and all associated account lines.
Departments can differ per line while date, business unit and location remain
the journal header context. Journal count is header count, not line count or
adjacent debit-credit pair count. The form includes per-line Department and
whole-journal debit, credit, difference and line count. An optional default
Department is a convenience for new lines.

The new bulk template uses `line_department_code (optional)` in column F.
Blank values remain unassigned. Repeat Document Number to identify all lines
of one journal, including nonadjacent rows. Department differences do not split
the document or conflict with its header. Validation and totals remain per
whole document. Each supplied department must be active and assigned to the
journal's location and business unit. Old files using `department_code` retain
their header-default behavior. Correction exports carry resolved old department
codes into the new per-line column.

Mixed department journals have no default department on the stored header;
department evidence remains on their individual lines. Uniform journals may
have a shared header department. No existing journals are rewritten.

Deploy backend first. No migration is required. Update the EC2 worker checkout
and restart `hmm-connect-export-worker` before using the new bulk template.
