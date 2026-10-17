# Catering P&L: PC LIPET template

Every Catering location uses the PC LIPET schedule from the supplied Template PL REV.xlsx, including Pekanbaru/head office and new locations. The location name appears in the heading and sheet name. There is no PC HO exception. Summary is first; one sheet follows per authorized location. Location sheets inside a Consolidated export use the same layout, and Hotel sheets retain their Hotel templates.

Static source rows, comparison columns, styles, spacing and subtotal positions are preserved. Figures are computed from each location's existing authorized report, never copied from the template. The summary aggregates the selected Catering scope. Missing budgets/comparisons stay blank. Explicit service-charge accounts are counted once; combined payroll accounts are not artificially split. Actual accounts without a template slot are retained before their subtotal.

The template's final Gross Operating Income / Profit / Loss row includes all related expenses, including overhead and under expenses, so it agrees with the report's final NOP for that location. No category mappings, journals, GL, opening balances or database records change. No migration is needed.
