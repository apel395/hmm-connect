import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { build } from "esbuild";
import JSZip from "jszip";
import * as XLSX from "xlsx";

const require = createRequire(import.meta.url);
const compiled = await build({
  absWorkingDir: path.resolve("."),
  tsconfig: path.resolve("tsconfig.app.json"),
  entryPoints: ["src/utils/generalLedgerExcel.ts"],
  bundle: true,
  write: false,
  platform: "node",
  format: "cjs",
  external: ["xlsx", "jszip"],
});
const module = { exports: {} };
new Function("module", "exports", "require", compiled.outputFiles[0].text)(module, module.exports, require);
const gl = module.exports;

const generatedAt = "2026-11-28T07:15:00.000Z";
const source = {
  brand_name: "MMH Connect",
  hotel_name: "Hotel Mutiara Merdeka",
  printed_by: "Bookkeeper",
  generated_at: generatedAt,
  period: { date_from: "2026-10-01", date_to: "2026-11-28" },
  filters: {
    account_code: "200-200-100",
    account_name: "Accrual Gaji",
    business_unit_name: "Hotel Operations",
    location_name: "Mutiara Merdeka",
    department_name: "Finance",
    reference_type: "JOURNAL",
    search_type: "ALL",
  },
  control: { total_debit: "0", total_credit: "3738694196" },
  accounts: [
    {
      account_id: 42,
      account_code: "200-200-100",
      account_name: "Accrual Gaji",
      normal_balance: "CREDIT",
      opening_balance: "9999064782",
      closing_balance: "13737758978",
      total_debit: "0",
      total_credit: "3738694196",
      rows: [
        {
          posting_date: "2026-10-28",
          journal_number: "MAN-202611-009470",
          document_number: "PAYROLL-10",
          description: "Payroll Oct 26 PT",
          location_name: "HO",
          department_name: "Finance",
          reference: "REF-470",
          debit: "0",
          credit: "118127192",
          balance: "10117191974",
        },
        {
          posting_date: "2026-10-28",
          journal_number: "MAN-202611-009471",
          document_number: "PAYROLL-10",
          description: "Payroll Oct 26 HO",
          location_name: "HO",
          department_name: "Finance",
          reference: "REF-471",
          debit: "0",
          credit: "57132315",
          balance: "10174324289",
        },
        {
          posting_date: "2026-10-28",
          journal_number: "MAN-202611-009472",
          document_number: "PAYROLL-10",
          description: "Payroll Oct 26 ZAMPED",
          location_name: "ZAMPED",
          department_name: "Finance",
          reference: "REF-472",
          debit: "0",
          credit: "122541192",
          balance: "10296865481",
        },
        {
          posting_date: "2026-11-28",
          journal_number: "MAN-202611-009475",
          document_number: "PAYROLL-11",
          description: "Other posted payroll movements",
          location_name: "HO",
          department_name: "Finance",
          reference: "REF-475",
          debit: "0",
          credit: "3440893497",
          balance: "13737758978",
        },
      ],
    },
  ],
};

const criteria = { date_from: "2026-10-01", date_to: "2026-11-28", account_ids: "42" };
const report = gl.buildGeneralLedgerReport(source, criteria);
assert.equal(report.title, "GENERAL LEDGER");
assert.equal(report.account, "200-200-100 · Accrual Gaji");
assert.equal(report.normalBalance, "CREDIT");
assert.equal(report.period, "01 October 2026 – 28 November 2026");
assert.ok(report.info.some((row) => row.label === "BUSINESS UNIT" && row.value === "Hotel Operations"));
assert.ok(report.info.some((row) => row.label === "SOURCE" && row.value === "General ledger print preview"));
assert.ok(!JSON.stringify(report).includes("Row Type"));
assert.ok(!JSON.stringify(report).includes("Difference"));

const safeJson = gl.serializeGLReport({ ...report, account: "Accrual <script> & Gaji" });
assert.ok(!safeJson.includes("<"), "inline model cannot close the script tag");
assert.deepEqual(JSON.parse(safeJson).account, "Accrual <script> & Gaji");

const { workbook, meta } = gl.buildGeneralLedgerWorkbook(report);
const printModel = JSON.parse(gl.serializeGLReport(report));
const fromPrintModel = gl.buildGeneralLedgerWorkbook(printModel).workbook;
assert.deepEqual(fromPrintModel.SheetNames, workbook.SheetNames, "page and print exports use the same sheets");
assert.deepEqual(fromPrintModel.Sheets, workbook.Sheets, "page and print exports use the same cells and template");
assert.deepEqual(workbook.SheetNames, ["General Ledger", "Report Info"]);
assert.equal(meta.printLayout.headerRow, 5);
const sheet = workbook.Sheets["General Ledger"];
assert.equal(sheet.A1.v, "GENERAL LEDGER");
assert.equal(sheet.B1.v, "MMH Connect");
assert.equal(sheet.C1.v, "Hotel Mutiara Merdeka");
assert.equal(sheet.A2.v, "ACCOUNT");
assert.equal(sheet.B2.v, "200-200-100 · Accrual Gaji");
assert.equal(sheet.C2.v, "NORMAL BALANCE");
assert.equal(sheet.D2.v, "CREDIT");
assert.equal(sheet.A3.v, "OPENING BALANCE");
assert.equal(sheet.J3.v, 9999064782);
assert.equal(sheet.J3.t, "n");
assert.equal(sheet.A4.v, "Transactions");

const expectedHeaders = [
  ["A", "Posting Date"],
  ["B", "Journal Number"],
  ["C", "Source Document"],
  ["D", "Description"],
  ["E", "Location"],
  ["F", "Department"],
  ["G", "Reference"],
  ["H", "Debit"],
  ["I", "Credit"],
  ["J", "Running Balance"],
];
for (const [column, label] of expectedHeaders) assert.equal(sheet[`${column}5`].v, label);

const visibleValues = Object.values(sheet)
  .filter((cell) => cell && typeof cell === "object" && "v" in cell)
  .map((cell) => String(cell.v));
for (const technical of ["Row Type", "Account Code", "LINE", "OPENING", "CONTROL", "Difference"]) {
  assert.ok(!visibleValues.includes(technical), `GL worksheet hides ${technical}`);
}
assert.equal(visibleValues.filter((value) => value === "200-200-100 · Accrual Gaji").length, 1, "account is named once");

assert.equal(sheet.A6.t, "d", "posting dates are native Excel dates");
assert.equal(sheet.A6.v.toISOString().slice(0, 10), "2026-10-28");
assert.equal(sheet.H6.v, 0);
assert.equal(sheet.I6.v, 118127192);
assert.equal(sheet.J6.v, 10117191974);
assert.equal(sheet.I9.v, 3440893497);
assert.equal(sheet.J9.v, 13737758978, "final running balance matches the closing balance");
assert.equal(sheet["!autofilter"].ref, "A5:J9");

assert.equal(sheet.A10.v, "Opening Balance");
assert.equal(sheet.J10.f, "J3");
assert.equal(sheet.A11.v, "Total Debit Movement");
assert.equal(sheet.J11.f, "SUM(H6:H9)");
assert.equal(sheet.A12.v, "Total Credit Movement");
assert.equal(sheet.J12.f, "SUM(I6:I9)");
assert.equal(sheet.A13.v, "Net Movement");
assert.equal(sheet.J13.f, "SUM(I6:I9)-SUM(H6:H9)", "credit-normal net movement is credit less debit");
assert.equal(sheet.J13.v, 3738694196);
assert.equal(sheet.A14.v, "Closing Balance");
assert.equal(sheet.J14.f, "J3+J13");
assert.equal(sheet.J14.v, 13737758978);
assert.ok(!visibleValues.includes("DIFFERENCE"));

const info = workbook.Sheets["Report Info"];
assert.equal(info.A1.v, "REPORT INFO");
const infoLabels = Object.values(info)
  .filter((cell) => cell && typeof cell === "object" && typeof cell.v === "string")
  .map((cell) => cell.v);
for (const label of ["REPORT", "ENTITY", "HOTEL", "PERIOD", "ACCOUNT", "PRINTED BY", "GENERATED AT", "REPORT CRITERIA"]) {
  assert.ok(infoLabels.includes(label), `Report Info carries ${label}`);
}
const checkRow = Number(
  Object.keys(info)
    .find((reference) => /^A\d+$/.test(reference) && info[reference].v === "RUNNING BALANCE CHECK")
    ?.slice(1),
);
assert.ok(checkRow > 0, "Report Info includes the running-balance control check");
assert.match(info[`B${checkRow}`].f, /'General Ledger'!J9='General Ledger'!J14/);

const names = (workbook.Workbook.Names ?? []).map((name) => name.Name);
assert.ok(names.includes("_xlnm.Print_Area"), "workbook defines a print area");
assert.ok(names.includes("_xlnm.Print_Titles"), "workbook repeats the transaction header on printed pages");

const bytes = await gl.writeGeneralLedgerWorkbook(report);
const sample = "/tmp/opencode/gl-accrual-gaji.xlsx";
fs.mkdirSync(path.dirname(sample), { recursive: true });
fs.writeFileSync(sample, bytes);

const zip = await JSZip.loadAsync(bytes);
const sheetXml = await zip.file("xl/worksheets/sheet1.xml").async("string");
assert.match(sheetXml, /showGridLines="0"/, "worksheet gridlines are hidden");
assert.match(sheetXml, /ySplit="5"/, "transaction header is frozen");
assert.match(sheetXml, /<sheetPr><pageSetUpPr fitToPage="1"\/><\/sheetPr>/, "fit-to-page printing is enabled");
assert.match(sheetXml, /<printOptions[^>]*gridLines="0"/, "print gridlines are disabled");
assert.match(sheetXml, /orientation="landscape"/, "print layout is landscape");
assert.match(sheetXml, /fitToWidth="1"/, "all columns fit one page wide");
assert.match(sheetXml, /fitToHeight="0"/, "rows are not forced onto one page");
assert.match(sheetXml, /<oddFooter>&amp;CPage &amp;P of &amp;N<\/oddFooter>/, "printed pages are numbered");
assert.match(sheetXml, /ht="19"/, "transaction rows use compact 19-point height");
const stylesXml = await zip.file("xl/styles.xml").async("string");
assert.match(stylesXml, /<b\/>/, "accounting styles include bold headings");
assert.match(stylesXml, /FF1F4E3D/, "table headers use an understated accounting fill");
assert.match(stylesXml, /numFmtId="164" formatCode="#,##0\.00"/, "money uses Indonesian-style two decimals");
assert.match(stylesXml, /numFmtId="165" formatCode="dd\/mm\/yy"/, "dates use a readable short format");
const boldFont = [...stylesXml.matchAll(/<font>[\s\S]*?<\/font>/g)]
  .map((match) => match[0])
  .find((entry) => entry.includes("<b/>"));
assert.ok(boldFont, "styles include a bold font");
assert.deepEqual(
  [...boldFont.matchAll(/<(b|i|strike|condense|extend|outline|shadow|u|vertAlign|sz|color|name|family|charset|scheme)\b/g)].map((match) => match[1]),
  ["b", "sz", "color", "name", "family"],
  "font children stay in the order Excel requires",
);
const fullBorder = [...stylesXml.matchAll(/<border>[\s\S]*?<\/border>/g)]
  .map((match) => match[0])
  .find((entry) => (entry.match(/style="thin"/g) ?? []).length === 4);
assert.ok(fullBorder, "styles include a full cell border");
assert.deepEqual(
  [...fullBorder.matchAll(/<(left|right|top|bottom|diagonal)\b/g)].map((match) => match[1]),
  ["left", "right", "top", "bottom", "diagonal"],
  "border children stay in the order Excel requires",
);
const workbookXml = await zip.file("xl/workbook.xml").async("string");
assert.match(workbookXml, /_xlnm\.Print_Area/);
assert.match(workbookXml, /_xlnm\.Print_Titles/);

const parsed = XLSX.read(bytes, { type: "array", cellDates: true });
assert.deepEqual(parsed.SheetNames, ["General Ledger", "Report Info"]);
const parsedSheet = parsed.Sheets["General Ledger"];
assert.equal(parsedSheet.J14.v, 13737758978);
assert.equal(parsedSheet.A6.t, "d");
assert.equal(parsedSheet.J4?.v ?? parsedSheet.J3.v, 9999064782);

const emptyReport = gl.buildGeneralLedgerReport(
  {
    ...source,
    accounts: [
      {
        ...source.accounts[0],
        rows: [],
        total_debit: "0",
        total_credit: "0",
        closing_balance: "9999064782",
      },
    ],
  },
  criteria,
);
const emptyWorkbook = gl.buildGeneralLedgerWorkbook(emptyReport).workbook;
const emptySheet = emptyWorkbook.Sheets["General Ledger"];
assert.equal(emptySheet.D6.v, "No movements in this period");
assert.equal(emptySheet.J8.v, 0);
assert.equal(emptySheet.J8.f, undefined, "zero-transaction reports do not point at empty SUM ranges");
assert.equal(emptySheet.J11.v, 9999064782);

const debitNormal = gl.buildGeneralLedgerReport(
  {
    ...source,
    accounts: [
      {
        ...source.accounts[0],
        normal_balance: "DEBIT",
        opening_balance: "1000",
        closing_balance: "1250",
        total_debit: "300",
        total_credit: "50",
        rows: [
          {
            posting_date: "2026-11-01",
            journal_number: "JV-1",
            debit: "300",
            credit: "50",
            balance: "1250",
          },
        ],
      },
    ],
  },
  criteria,
);
const debitWorkbook = gl.buildGeneralLedgerWorkbook(debitNormal).workbook;
const debitSheet = debitWorkbook.Sheets["General Ledger"];
const debitNetRow = Number(
  Object.keys(debitSheet)
    .find((reference) => /^A\d+$/.test(reference) && debitSheet[reference].v === "Net Movement")
    ?.slice(1),
);
assert.match(debitSheet[`J${debitNetRow}`].f, /SUM\(H\d+:H\d+\)-SUM\(I\d+:I\d+\)/, "debit-normal net movement is debit less credit");
assert.equal(debitSheet[`J${debitNetRow}`].v, 250);

const multiReport = gl.buildGeneralLedgerReport(
  {
    ...source,
    accounts: [
      source.accounts[0],
      {
        ...source.accounts[0],
        account_id: 43,
        account_code: "400-100-100",
        account_name: "Room Revenue",
        normal_balance: "CREDIT",
        opening_balance: "500",
        closing_balance: "700",
        total_debit: "0",
        total_credit: "200",
        rows: [
          {
            posting_date: "2026-11-02",
            journal_number: "JV-2",
            debit: "0",
            credit: "200",
            balance: "700",
          },
        ],
      },
    ],
  },
  criteria,
);
const multiWorkbook = gl.buildGeneralLedgerWorkbook(multiReport).workbook;
const multiSheet = multiWorkbook.Sheets["General Ledger"];
assert.equal(multiSheet.A3.v, "Opening balance is shown above each account");
const openingLabels = Object.keys(multiSheet)
  .filter((reference) => /^A\d+$/.test(reference) && multiSheet[reference].v === "OPENING BALANCE")
  .map((reference) => Number(reference.slice(1)));
assert.equal(openingLabels.length, 2, "each account gets one opening balance in a multi-account report");
const multiLines = Object.keys(multiSheet)
  .filter((reference) => /^B\d+$/.test(reference) && String(multiSheet[reference].v).startsWith("MAN-"))
  .map((reference) => Number(reference.slice(1)));
assert.ok(
  multiLines.every((row) => multiSheet[`A${row}`].t === "d"),
  "transaction rows never repeat account code and name",
);

console.log(
  `GL Excel PASS: compact two-sheet workbook, native dates/numbers, formula reconciliation, frozen filter header, print setup and styling. Sample: ${sample}`,
);
