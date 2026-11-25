/* global require, __dirname, console */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");
const has = (file, tokens, label) => {
  const source = read(file);
  for (const token of tokens) {
    assert.ok(source.includes(token), `${label}: ${file} missing ${JSON.stringify(token)}`);
  }
};
function run() {
  const admin = "src/modules/admin/";
  has(`${admin}users/UserPage.tsx`, ["DataWorkspace", "ModuleSummary", "Loading", "Empty", "apiErrorMessage"], "Users");
  has(`${admin}users/UserPage.tsx`, ["WorkspaceFilters", "aria-label=\"Filters\""], "Users filter context");
  has(`${admin}roles/RolePage.tsx`, ["DataWorkspace", "WorkspaceFilters", "ModuleSummary", "Loading", "Empty", "apiErrorMessage"], "Roles");
  has(`${admin}roles/RolePage.tsx`, ["CORE_ROLES", "window.confirm"], "Roles behavior preserved");
  has(`${admin}sessions/ActiveSessionsPage.tsx`, ["DataWorkspace", "ModuleSummary", "Loading", "Empty", "apiErrorMessage"], "Active Sessions");
  has(`${admin}sessions/ActiveSessionsPage.tsx`, ["window.confirm", "useActiveSessions"], "Active Sessions behavior preserved");

  has("src/modules/approval/ApprovalConfigurationPage.tsx", ["DataWorkspace", "ModuleSummary", "Loading", "Empty", "apiErrorMessage", "Badge"], "Approval Configuration");
  has("src/modules/audit/AuditLogPage.tsx", ["DataWorkspace", "WorkspaceFilters", "ModuleSummary", "Loading", "Empty", "apiErrorMessage"], "Audit Log");
  has("src/modules/audit/AuditLogPage.tsx", ["placeholderData", "previousData"], "Audit Log pagination preserved");
  has("src/modules/audit/TraceabilityPage.tsx", ["DataWorkspace", "Loading", "Empty", "apiErrorMessage", "WorkspaceBackButton"], "Traceability");
  has("src/modules/audit/TraceabilityPage.tsx", ["purchase-orders", "purchase-requisitions"], "Traceability mapping preserved");

  has("src/modules/finance/setup/ReportSetupPage.tsx", ["Loading", "Empty", "apiErrorMessage", "PROFIT_LOSS", "BALANCE_SHEET"], "Report Setup");
  has("src/modules/finance/statistics/StatisticsPage.tsx", ["DataWorkspace", "WorkspaceFilters", "ModuleSummary", "Loading", "Empty", "apiErrorMessage", "Pagination"], "Statistics");
  has("src/modules/finance/posting-rules/PostingRulesPage.tsx", ["DataWorkspace", "ModuleSummary", "Loading", "Empty", "apiErrorMessage", "PrintPreviewButton"], "Posting Rules");
  has("src/modules/finance/posting-rules/PostingRulesPage.tsx", ["/accounting/direct-coa-settings", "/finance-setup/posting-rules/print"], "Posting Rules endpoints preserved");

  console.log("Admin and Finance setup PASS: shared workspace shell, explicit states, preserved behavior.");
}

run();
