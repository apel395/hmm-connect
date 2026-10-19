import path from "node:path";
import console from "node:console";
import { URLSearchParams } from "node:url";
import assert from "node:assert/strict";
import { build } from "esbuild";
import { createRequire } from "node:module";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
const require = createRequire(import.meta.url);
async function compile(entry) {
  const result = await build({ entryPoints: [entry], alias: { "@": path.resolve("src") }, bundle: true, write: false, platform: "node", format: "cjs", jsx: "automatic", define: { "import.meta.env.VITE_API_URL": JSON.stringify("https://test.invalid") }, external: ["react", "react/jsx-runtime"], plugins: [{ name: "browser-services", setup(build) {
    build.onResolve({ filter: /^(@\/api\/client|@\/store\/auth)$/ }, args => ({ path: args.path, namespace: "mock" }));
    build.onLoad({ filter: /.*/, namespace: "mock" }, () => ({ contents: "export default {};", loader: "js" }));
  }}] });
  const module = { exports: {} };
  new Function("module", "exports", "require", result.outputFiles[0].text)(module, module.exports, require);
  return module.exports;
}
const storage = await compile("src/utils/formDraftStorage.ts");
const memory = new Map();
const browser = { getItem: key => memory.get(key) ?? null, setItem: (key, value) => memory.set(key, value), removeItem: key => memory.delete(key) };
const valid = v => v && typeof v.description === "string" && Array.isArray(v.lines);
const value = { description: "Journal not submitted", postingDate: "2026-01-05", lines: [{ account_id: 215, debit: 5500000, credit: 0 }] };
const createKey = storage.draftKey("45", "journal:create");
assert.equal(storage.writeDraft(browser, createKey, value), true);
assert.deepEqual(storage.readDraft(browser, createKey, valid), value);
assert.equal(storage.readDraft(browser, storage.draftKey("46", "journal:create"), valid), null);
assert.equal(storage.readDraft(browser, storage.draftKey("45", "journal:edit:1344"), valid), null);
const editKey = storage.draftKey("45", "journal:edit:1344");
storage.writeDraft(browser, editKey, { ...value, description: "Edit" });
storage.removeDraft(browser, createKey);
assert.equal(storage.readDraft(browser, createKey, valid), null);
assert.equal(storage.readDraft(browser, editKey, valid).description, "Edit");
browser.setItem(createKey, '{"version":99,"value":{}}');
assert.equal(storage.readDraft(browser, createKey, valid), null);
browser.setItem(createKey, 'broken JSON');
assert.equal(storage.readDraft(browser, createKey, valid), null);
assert.equal(storage.writeDraft({ setItem() { throw new Error("Quota exceeded"); } }, createKey, value), false);
console.log("Input recovery: round trip, user/document isolation, discard, corrupt/versioned storage and storage failure passed.");
const { FinancialStatementPrint } = await compile("src/modules/finance/financial-statements/FinancialReportPrintPage.tsx");
const amounts = current => ({ current: String(current), budget: null, last_month: String(current), last_year: null, variance: null, movement: "0" });
const data = { header_only: false, scope: { location_id: 1, business_unit_id: 1, department_id: null }, scope_labels: { location_id: "Pekanbaru", business_unit_id: "Hotel" }, periods: { MTD: { current: ["2026-10-01", "2026-10-06"] }, YTD: { current: ["2026-01-01", "2026-10-06"] } }, rows: [], section_totals: {} };
for (const [section, number] of [["REVENUE", 100], ["COST_OF_REVENUE", 130], ["EXPENSES", 20], ["ASSETS", 5500000], ["LIABILITIES", 4000000], ["EQUITY", -4025000]]) {
  data.section_totals[section] = { MTD: amounts(number), YTD: amounts(number) };
  data.rows.push({ section, account_code: section === "REVENUE" ? "400" : "100-600-104", account_name: "Full account name <script> & equipment", account_ids: [215], periods: data.section_totals[section] });
}
const pnl = renderToStaticMarkup(createElement(FinancialStatementPrint, { kind: "PROFIT_LOSS", data, asOf: "2026-10-06", printedBy: "Finance" }));
assert.match(pnl, /MTD/); assert.match(pnl, /YTD/); assert.match(pnl, /Pekanbaru/); assert.match(pnl, /2026-01-01/);
assert.match(pnl, /-50,00/); assert.match(pnl, /—/); assert.match(pnl, /&lt;script&gt;/); assert.doesNotMatch(pnl, /<script>/);
assert.match(pnl, /table-header-group/); assert.match(pnl, /break-inside:avoid/);
const balance = renderToStaticMarkup(createElement(FinancialStatementPrint, { kind: "BALANCE_SHEET", data, asOf: "2026-10-06" }));
assert.match(balance, /statement-t/);
assert.match(balance, /<tr class="grand-total paired-totals">[^]*?Total Aset[^]*?Total Liabilitas \+ Ekuitas[^]*?<\/tr>/);
assert.equal((balance.match(/class="grand-total paired-totals"/g) ?? []).length, 1); assert.equal((balance.match(/<section class="comparison-page"/g) ?? []).length, 2);
assert.match(balance, /-4\.025\.000,00/); assert.match(balance, /-25\.000,00/);
assert.match(balance, /Saldo per 2026-10-06/); assert.doesNotMatch(balance, /<button/);
const kap = renderToStaticMarkup(createElement(FinancialStatementPrint, { kind: "BALANCE_SHEET", data: { ...data, header_only: true }, asOf: "2026-10-06" }));
assert.match(kap, /NERACA — KAP/);
assert.match(kap, /A4 portrait/);
assert.equal((kap.match(/<section class="comparison-page"/g) ?? []).length, 0);
console.log("Print rendering: grouped comparisons, signed totals, unavailable values, escaped full names, T layout, separate comparisons and KAP heading passed.");

const reportState = await compile("src/modules/finance/financial-statements/reportState.ts");
const defaults = { as_of_date: "2026-10-13", business_unit_id: "", location_id: "", department_id: "", budget_id: "", kap: false, include_zero: false, report_scope: "CONSOLIDATED" };
const selected = { filters: { ...defaults, as_of_date: "2026-01-31", location_id: "8", department_id: "7", budget_id: "2", kap: true }, period: "YTD", view: "EXECUTIVE" };
reportState.saveReportPreferences("45", "BALANCE_SHEET", selected, browser);
assert.deepEqual(reportState.loadReportPreferences("45", "BALANCE_SHEET", "", defaults, browser), selected);
assert.equal(reportState.loadReportPreferences("46", "BALANCE_SHEET", "", defaults, browser).filters.as_of_date, defaults.as_of_date);
assert.equal(reportState.loadReportPreferences("45", "PROFIT_LOSS", "", defaults, browser).filters.as_of_date, defaults.as_of_date);
const explicit = reportState.loadReportPreferences("45", "BALANCE_SHEET", "?as_of_date=2026-02-28&location_id=1", defaults, browser);
assert.equal(explicit.filters.as_of_date, "2026-02-28");
assert.equal(explicit.filters.location_id, "1");
assert.equal(explicit.filters.department_id, "");
assert.equal(explicit.filters.budget_id, "");
console.log("Report preferences: retained date/scope/view, explicit link precedence and user/report isolation passed.");

const api = (await compile("src/api/client.ts")).default;
let redirected = "";
globalThis.localStorage = browser;
globalThis.window = { location: { replace: route => { redirected = route; } } };
storage.writeDraft(browser, createKey, value);
browser.setItem("access_token", "expired-session"); browser.setItem("refresh_token", "refresh"); browser.setItem("user", "user");
const expiredConfig = api.interceptors.request.handlers[0].fulfilled({ url: "/test", method: "get", headers: {} });
assert.equal(expiredConfig.headers.Authorization, "Bearer expired-session");
await api.interceptors.response.handlers[0].rejected({ config: expiredConfig, response: { status: 401 } }).catch(() => {});
assert.equal(browser.getItem("access_token"), null);
assert.deepEqual(storage.readDraft(browser, createKey, valid), value);
assert.equal(redirected, "/login?reason=session");
browser.setItem("access_token", "old-session");
const staleConfig = api.interceptors.request.handlers[0].fulfilled({ url: "/test", method: "get", headers: {} });
browser.setItem("access_token", "new-session");
await api.interceptors.response.handlers[0].rejected({ config: staleConfig, response: { status: 401 } }).catch(() => {});
assert.equal(browser.getItem("access_token"), "new-session");
console.log("Session expiry PASS: saved input retained, credentials cleared, stale 401 cannot erase a replacement login.");

const { ledgerPrintParams } = await compile("src/modules/finance/general-ledger/printFilters.ts");
const ledgerFilters = ledgerPrintParams(new URLSearchParams("account_ids=211,215&account_from_id=211&account_to_id=215&search_type=DOCUMENT&search=INV-1&location_id=1&business_unit_id=2&department_id=3&date_from=2026-01-01&date_to=2026-10-07"));
assert.equal(ledgerFilters.account_ids, "211,215");
assert.equal(ledgerFilters.account_from_id, "211");
assert.equal(ledgerFilters.account_to_id, "215");
assert.equal(ledgerFilters.search_type, "DOCUMENT");
assert.equal(ledgerFilters.search, "INV-1");
assert.equal(ledgerFilters.location_id, "1");
assert.equal(ledgerFilters.business_unit_id, "2");
assert.equal(ledgerFilters.department_id, "3");
assert.equal(ledgerFilters.date_from, "2026-01-01");
assert.equal(ledgerFilters.date_to, "2026-10-07");
assert.equal(ledgerFilters.account_id, undefined);
console.log("GL print scope PASS: exact account IDs, ranges, search type, dates and dimensions retained.");

const departmentData = { ...data, department_reports: [
  { department_id: 8, department_name: "House Keeping", rows: data.rows, section_totals: data.section_totals },
  { department_id: null, department_name: "Unassigned department", rows: data.rows, section_totals: data.section_totals },
] };
const departmentPrint = renderToStaticMarkup(createElement(FinancialStatementPrint, { kind: "PROFIT_LOSS", data: departmentData, asOf: "2026-10-06" }));
assert.equal((departmentPrint.match(/class="department-statement/g) ?? []).length, 0);
assert.doesNotMatch(departmentPrint, /House Keeping — MTD/);
assert.doesNotMatch(departmentPrint, /House Keeping — YTD/);
assert.doesNotMatch(departmentPrint, /Unassigned department — MTD/);
assert.doesNotMatch(departmentPrint, /100-600-104/);
assert.match(departmentPrint, /Full account name &lt;script&gt; &amp; equipment/);
console.log("P&L print PASS: single scoped report without department tables, account codes hidden.");

const managementData = { ...departmentData, report_scope: "HOTEL", balance_control: {difference:"123.00",is_balanced:false}, presentation_rows: [
  {key:"REVENUE",label:"Pendapatan Hotel",kind:"category",account_ids:[1],periods:{MTD:data.section_totals.REVENUE.MTD,YTD:data.section_totals.REVENUE.YTD}},
  {key:"GOI",label:"Gross Operating Income / Loss",kind:"subtotal",account_ids:[],periods:{MTD:data.section_totals.REVENUE.MTD,YTD:data.section_totals.REVENUE.YTD}},
  {key:"NOP",label:"Net Operating Profit / Loss",kind:"subtotal",account_ids:[],periods:{MTD:data.section_totals.REVENUE.MTD,YTD:data.section_totals.REVENUE.YTD}}
]};
const managementPrint = renderToStaticMarkup(createElement(FinancialStatementPrint,{kind:"PROFIT_LOSS",data:managementData,asOf:"2026-10-06"}));
assert.match(managementPrint,/Gross Operating Income/);assert.match(managementPrint,/Net Operating Profit/);assert.doesNotMatch(managementPrint,/Not balanced/);assert.doesNotMatch(managementPrint,/House Keeping/);assert.doesNotMatch(managementPrint,/100-600-104/);
console.log("Management P&L print PASS: single statement, management subtotals without balance notices.");

const unbalancedPrint = renderToStaticMarkup(createElement(FinancialStatementPrint, { kind: "BALANCE_SHEET", data: { ...data, balance_control: { difference: "5525000", is_balanced: false } }, asOf: "2026-10-06" }));
assert.match(unbalancedPrint, /Out of balance/);
assert.match(unbalancedPrint, /5\.525\.000/);
assert.doesNotMatch(unbalancedPrint, />Balanced</);
const balancedPrint = renderToStaticMarkup(createElement(FinancialStatementPrint, { kind: "BALANCE_SHEET", data: { ...data, header_only: true, balance_control: { difference: "0", is_balanced: true } }, asOf: "2026-10-06" }));
assert.match(balancedPrint, />Balanced</);
assert.doesNotMatch(balancedPrint, /Out of balance/);
console.log("Balance status: balanced KAP and unbalanced detail print evidence passed.");

const { selectRelatedAccounts } = await compile("src/modules/finance/financial-statements/reportAttribution.ts");
const sharedCoa=[{account_id:20,presentation_key:"food",category:"COST_OF_REVENUE"},{account_id:20,presentation_key:"testing",category:"OPERATING_EXPENSE"}];
assert.deepEqual(selectRelatedAccounts(sharedCoa,{account_ids:[20],member_keys:["food"]}),[sharedCoa[0]]);
assert.deepEqual(selectRelatedAccounts(sharedCoa,{account_ids:[20],member_keys:["testing"]}),[sharedCoa[1]]);
assert.deepEqual(selectRelatedAccounts(sharedCoa,{account_ids:[20]}),sharedCoa);
assert.deepEqual(selectRelatedAccounts(sharedCoa,null),[]);
console.log("P&L attribution drilldown: same COA split by category, subtotal membership and legacy API compatibility passed.");
