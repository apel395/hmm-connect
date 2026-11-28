import * as JSZip from "jszip";
import * as XLSX from "xlsx";
import { moneyNumber } from "./formatMoney";

export const GL_SHEET = "General Ledger";
export const GL_INFO_SHEET = "Report Info";

const MONEY_FORMAT = "#,##0.00";
const DATE_FORMAT = "dd/mm/yy";
const MONEY_FMT_ID = 164;
const DATE_FMT_ID = 165;

const HEADERS = [
  "Posting Date",
  "Journal Number",
  "Source Document",
  "Description",
  "Location",
  "Department",
  "Reference",
  "Debit",
  "Credit",
  "Running Balance",
] as const;

const WIDTHS = [14, 22, 24, 44, 18, 16, 22, 18, 18, 20];

type StyleKey =
  | "title"
  | "subtitle"
  | "label"
  | "value"
  | "account"
  | "header"
  | "text"
  | "altText"
  | "date"
  | "altDate"
  | "money"
  | "altMoney"
  | "balance"
  | "altBalance"
  | "section"
  | "totalLabel"
  | "totalMoney"
  | "infoLabel"
  | "infoValue"
  | "check";

const STYLE_ORDER: StyleKey[] = [
  "title",
  "subtitle",
  "label",
  "value",
  "account",
  "header",
  "text",
  "altText",
  "date",
  "altDate",
  "money",
  "altMoney",
  "balance",
  "altBalance",
  "section",
  "totalLabel",
  "totalMoney",
  "infoLabel",
  "infoValue",
  "check",
];

interface StyleDefinition {
  font: number;
  fill: number;
  border: number;
  format?: number;
  align?: "left" | "center" | "right";
  wrap?: boolean;
}

const STYLES: Record<StyleKey, StyleDefinition> = {
  title: { font: 1, fill: 0, border: 0, align: "left" },
  subtitle: { font: 2, fill: 0, border: 0, align: "left" },
  label: { font: 3, fill: 4, border: 0, align: "left" },
  value: { font: 0, fill: 4, border: 0, align: "left" },
  account: { font: 5, fill: 4, border: 0, align: "left" },
  header: { font: 6, fill: 2, border: 3, align: "center", wrap: true },
  text: { font: 0, fill: 0, border: 1, align: "left", wrap: true },
  altText: { font: 0, fill: 3, border: 1, align: "left", wrap: true },
  date: { font: 0, fill: 0, border: 1, format: DATE_FMT_ID, align: "center" },
  altDate: { font: 0, fill: 3, border: 1, format: DATE_FMT_ID, align: "center" },
  money: { font: 0, fill: 0, border: 1, format: MONEY_FMT_ID, align: "right" },
  altMoney: { font: 0, fill: 3, border: 1, format: MONEY_FMT_ID, align: "right" },
  balance: { font: 3, fill: 0, border: 1, format: MONEY_FMT_ID, align: "right" },
  altBalance: { font: 3, fill: 3, border: 1, format: MONEY_FMT_ID, align: "right" },
  section: { font: 3, fill: 4, border: 0, align: "left" },
  totalLabel: { font: 3, fill: 5, border: 2, align: "left" },
  totalMoney: { font: 3, fill: 5, border: 2, format: MONEY_FMT_ID, align: "right" },
  infoLabel: { font: 3, fill: 4, border: 1, align: "left" },
  infoValue: { font: 0, fill: 0, border: 1, align: "left", wrap: true },
  check: { font: 3, fill: 4, border: 1, align: "center" },
};

export interface GLExcelLine {
  posting_date?: string | null;
  journal_number?: string | null;
  document_number?: string | null;
  document_type?: string | null;
  reference?: string | null;
  description?: string | null;
  location_name?: string | null;
  department_name?: string | null;
  debit?: string | number | null;
  credit?: string | number | null;
  balance?: string | number | null;
}

export interface GLExcelAccount {
  account_id?: string | number;
  account_code: string;
  account_name: string;
  account_type?: string | null;
  normal_balance?: string | null;
  opening_balance?: string | number | null;
  closing_balance?: string | number | null;
  total_debit?: string | number | null;
  total_credit?: string | number | null;
  rows?: GLExcelLine[];
}

export interface GLExcelPrintData {
  accounts?: GLExcelAccount[];
  control?: { total_debit?: string | number | null; total_credit?: string | number | null } | null;
  filters?: Record<string, unknown> | null;
  period?: { date_from?: string | null; date_to?: string | null } | null;
  brand_name?: string | null;
  hotel_name?: string | null;
  printed_by?: string | null;
  generated_at?: string | null;
}

export interface GLExcelInfoRow {
  label: string;
  value: string;
}

export interface GLExcelReport {
  title: string;
  company: string;
  hotel: string;
  period: string;
  account: string;
  normalBalance: string;
  accounts: GLExcelAccount[];
  info: GLExcelInfoRow[];
  criteria: Record<string, string>;
}

interface GLWorkbookMeta {
  styleMaps: Record<number, Record<string, StyleKey>>;
  printLayout?: {
    headerRow: number;
    lastRow: number;
    lastTransactionRow: number;
  };
}

const text = (value: unknown) => (value == null || value === "" ? "—" : String(value));
const longDate = (value?: string | null) => {
  if (!value) return "";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value));
  if (!match) return String(value);
  const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  return `${match[3]} ${months[Number(match[2]) - 1] || match[2]} ${match[1]}`;
};

function excelDate(value: unknown): Date | null {
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (!value) return null;
  const raw = String(value);
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(raw);
  if (match) return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12);
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/** JSON safe for an inline script: script text does not decode HTML entities. */
export function serializeGLReport(report: GLExcelReport) {
  return JSON.stringify(report)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026")
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029");
}

/** Build the presentation model from backend print data without recomputing amounts. */
export function buildGeneralLedgerReport(
  data: GLExcelPrintData,
  criteria: Record<string, string> = {},
): GLExcelReport {
  const filters = data.filters ?? {};
  const accounts = data.accounts ?? [];
  const first = accounts[0];
  const single = accounts.length === 1;
  const from = data.period?.date_from || criteria.date_from;
  const to = data.period?.date_to || criteria.date_to;
  const period = from || to
    ? `${longDate(from) || "…"} – ${longDate(to) || "…"}`
    : "All dates";
  const company = text(data.brand_name || "MMH Connect");
  const hotel = text(data.hotel_name);
  const account = single
    ? `${first.account_code} · ${first.account_name}`
    : text(filters.account_code)
      ? `${text(filters.account_code)} · ${text(filters.account_name)}`
      : "All accounts";
  const normalBalance = single ? text(first.normal_balance) : "See account sections";
  const info: GLExcelInfoRow[] = [
    { label: "REPORT", value: "GENERAL LEDGER" },
    { label: "ENTITY", value: company },
    { label: "HOTEL", value: hotel },
    { label: "PERIOD", value: period },
    { label: "ACCOUNT", value: account },
    { label: "NORMAL BALANCE", value: normalBalance },
    { label: "BUSINESS UNIT", value: text(filters.business_unit_name || criteria.business_unit_id || "All") },
    { label: "LOCATION", value: text(filters.location_name || criteria.location_id || "All") },
    { label: "DEPARTMENT", value: text(filters.department_name || criteria.department_id || "All") },
    { label: "REFERENCE TYPE", value: text(filters.reference_type || criteria.reference_type || "All") },
    { label: "SEARCH TYPE", value: text(filters.search_type || criteria.search_type || "All") },
    { label: "SEARCH", value: text(filters.search || criteria.search || "—") },
    { label: "SUPPLIER", value: text(filters.supplier_name || criteria.supplier_id || "All") },
    {
      label: "ACCOUNT RANGE",
      value: filters.account_from_code || filters.account_to_code
        ? `${text(filters.account_from_code)} – ${text(filters.account_to_code)}`
        : "All",
    },
    { label: "PRINTED", value: text(data.generated_at ? new Date(data.generated_at).toLocaleString("en-GB") : "—") },
    { label: "PRINTED BY", value: text(data.printed_by || "Finance") },
    { label: "GENERATED AT", value: text(data.generated_at || new Date().toISOString()) },
    { label: "TOTAL DEBIT MOVEMENT", value: String(moneyNumber(data.control?.total_debit)) },
    { label: "TOTAL CREDIT MOVEMENT", value: String(moneyNumber(data.control?.total_credit)) },
    { label: "SOURCE", value: "General ledger print preview" },
    { label: "REPORT CRITERIA", value: JSON.stringify(criteria) },
  ];

  return {
    title: "GENERAL LEDGER",
    company,
    hotel,
    period,
    account,
    normalBalance,
    accounts,
    info,
    criteria,
  };
}

function columnName(index: number) {
  let value = index + 1;
  let name = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    name = String.fromCharCode(65 + remainder) + name;
    value = Math.floor((value - 1) / 26);
  }
  return name;
}

function createSheet() {
  const sheet: Record<string, unknown> = {};
  const styleMap: Record<string, StyleKey> = {};
  const put = (
    address: string,
    value: unknown,
    style: StyleKey,
    options: { formula?: string; type?: "n" | "s" | "d"; format?: string } = {},
  ) => {
    const cell: Record<string, unknown> = {
      t: options.type ?? (typeof value === "number" ? "n" : "s"),
      v: options.type === "d" ? value : options.type === "n" ? moneyNumber(value) : text(value),
    };
    if (options.formula) cell.f = options.formula;
    if (options.format) cell.z = options.format;
    if (options.type === "n" || options.formula) cell.z = options.format ?? MONEY_FORMAT;
    sheet[address] = cell;
    styleMap[address] = style;
  };
  const putText = (address: string, value: unknown, style: StyleKey) => put(address, value, style, { type: "s" });
  const putMoney = (address: string, value: unknown, style: StyleKey, formula?: string) =>
    put(address, value, style, { type: "n", format: MONEY_FORMAT, formula });
  const putDate = (address: string, value: unknown, style: StyleKey) => {
    const parsed = excelDate(value);
    if (!parsed) putText(address, value, style);
    else put(address, parsed, style, { type: "d", format: DATE_FORMAT });
  };
  return { sheet, styleMap, put, putText, putMoney, putDate };
}

/** Build the two-sheet workbook. Amounts and dates become native Excel cells. */
export function buildGeneralLedgerWorkbook(report: GLExcelReport): {
  workbook: XLSX.WorkBook;
  meta: GLWorkbookMeta;
} {
  const workbook = XLSX.utils.book_new();
  const main = createSheet();
  const info = createSheet();
  const accounts = report.accounts ?? [];
  const single = accounts.length === 1;
  const headerRow = 5;
  let cursor = headerRow + 1;

  main.putText("A1", report.title, "title");
  main.putText("B1", report.company, "subtitle");
  main.putText("C1", report.hotel, "subtitle");
  main.putText("D1", report.period, "subtitle");
  main.putText("A2", "ACCOUNT", "label");
  main.putText("B2", report.account, "account");
  main.putText("C2", "NORMAL BALANCE", "label");
  main.putText("D2", report.normalBalance, "account");
  if (single) {
    main.putText("A3", "OPENING BALANCE", "label");
    main.putMoney("J3", accounts[0].opening_balance, "balance");
  } else {
    main.putText("A3", "Opening balance is shown above each account", "subtitle");
  }
  main.putText("A4", "Transactions", "section");
  HEADERS.forEach((label, index) => main.putText(`${columnName(index)}${headerRow}`, label, "header"));

  let lastTransactionRow = headerRow;
  let runningBalanceRow: number | undefined;
  let closingBalanceRow: number | undefined;

  const addSummary = (
    label: string,
    value: unknown,
    style: "totalLabel" | "label",
    formula?: string,
  ) => {
    const row = cursor++;
    main.putText(`A${row}`, label, style);
    main.putMoney(`J${row}`, value, "totalMoney", formula);
    return row;
  };

  accounts.forEach((account) => {
    const debitNormal = String(account.normal_balance || "").toUpperCase() === "DEBIT";
    let openingRow: number;
    if (!single) {
      const accountHeaderRow = cursor++;
      main.putText(`A${accountHeaderRow}`, "ACCOUNT", "label");
      main.putText(`B${accountHeaderRow}`, `${account.account_code} · ${account.account_name}`, "account");
      main.putText(`C${accountHeaderRow}`, "NORMAL BALANCE", "label");
      main.putText(`D${accountHeaderRow}`, text(account.normal_balance), "account");
      openingRow = cursor++;
      main.putText(`A${openingRow}`, "OPENING BALANCE", "label");
      main.putMoney(`J${openingRow}`, account.opening_balance, "balance");
    } else {
      openingRow = 3;
    }

    const lineStart = cursor;
    const rows = account.rows ?? [];
    if (!rows.length) {
      main.putText(`D${lineStart}`, "No movements in this period", "text");
      main.putMoney(`H${lineStart}`, 0, "money");
      main.putMoney(`I${lineStart}`, 0, "money");
      main.putMoney(`J${lineStart}`, account.closing_balance, "balance");
      cursor += 1;
    } else {
      rows.forEach((row, index) => {
        const alternate = index % 2 === 1;
        const dateStyle = alternate ? "altDate" : "date";
        const textStyle = alternate ? "altText" : "text";
        const moneyStyle = alternate ? "altMoney" : "money";
        const balanceStyle = alternate ? "altBalance" : "balance";
        main.putDate(`A${cursor}`, row.posting_date, dateStyle);
        main.putText(`B${cursor}`, row.journal_number, textStyle);
        main.putText(`C${cursor}`, row.document_number || row.document_type, textStyle);
        main.putText(`D${cursor}`, row.description, textStyle);
        main.putText(`E${cursor}`, row.location_name, textStyle);
        main.putText(`F${cursor}`, row.department_name, textStyle);
        main.putText(`G${cursor}`, row.reference, textStyle);
        main.putMoney(`H${cursor}`, row.debit, moneyStyle);
        main.putMoney(`I${cursor}`, row.credit, moneyStyle);
        main.putMoney(`J${cursor}`, row.balance, balanceStyle);
        runningBalanceRow = cursor;
        cursor += 1;
      });
    }
    const lineEnd = cursor - 1;
    lastTransactionRow = Math.max(lastTransactionRow, lineEnd);
    const hasLines = rows.length > 0;
    const debitFormula = hasLines ? `SUM(H${lineStart}:H${lineEnd})` : undefined;
    const creditFormula = hasLines ? `SUM(I${lineStart}:I${lineEnd})` : undefined;
    const totalDebit = moneyNumber(account.total_debit ?? rows.reduce((sum, row) => sum + moneyNumber(row.debit), 0));
    const totalCredit = moneyNumber(account.total_credit ?? rows.reduce((sum, row) => sum + moneyNumber(row.credit), 0));
    const opening = moneyNumber(account.opening_balance);
    const closing = moneyNumber(account.closing_balance);
    const net = closing - opening;

    addSummary("Opening Balance", opening, "totalLabel", `J${openingRow}`);
    addSummary("Total Debit Movement", totalDebit, "totalLabel", debitFormula);
    addSummary("Total Credit Movement", totalCredit, "totalLabel", creditFormula);
    const netRow = addSummary(
      "Net Movement",
      net,
      "totalLabel",
      hasLines
        ? debitNormal
          ? `${debitFormula}-${creditFormula}`
          : `${creditFormula}-${debitFormula}`
        : undefined,
    );
    closingBalanceRow = addSummary("Closing Balance", closing, "totalLabel", `J${openingRow}+J${netRow}`);
  });

  const lastRow = Math.max(cursor - 1, headerRow);
  main.sheet["!ref"] = `A1:J${lastRow}`;
  main.sheet["!cols"] = WIDTHS.map((wch) => ({ wch }));
  main.sheet["!rows"] = Array.from({ length: lastRow }, (_, index) => ({
    hpt: index === 0 ? 24 : index + 1 === headerRow ? 21 : 19,
  }));
  main.sheet["!autofilter"] = { ref: `A${headerRow}:J${Math.max(headerRow, lastTransactionRow)}` };
  main.sheet["!margins"] = { left: 0.3, right: 0.3, top: 0.5, bottom: 0.5, header: 0.2, footer: 0.2 };
  XLSX.utils.book_append_sheet(workbook, main.sheet as XLSX.WorkSheet, GL_SHEET);

  info.putText("A1", "REPORT INFO", "title");
  info.putText("A2", report.title, "subtitle");
  let infoRow = 4;
  report.info.forEach(({ label, value }) => {
    info.putText(`A${infoRow}`, label, "infoLabel");
    info.putText(`B${infoRow}`, value, "infoValue");
    infoRow += 1;
  });
  if (runningBalanceRow != null && closingBalanceRow != null) {
    info.putText(`A${infoRow}`, "RUNNING BALANCE CHECK", "infoLabel");
    info.sheet[`B${infoRow}`] = {
      t: "s",
      v: "OK",
      f: `IF('${GL_SHEET}'!J${runningBalanceRow}='${GL_SHEET}'!J${closingBalanceRow},"OK","REVIEW")`,
    };
    info.styleMap[`B${infoRow}`] = "check";
    infoRow += 1;
  }
  info.sheet["!ref"] = `A1:B${Math.max(infoRow - 1, 2)}`;
  info.sheet["!cols"] = [{ wch: 24 }, { wch: 92 }];
  info.sheet["!rows"] = Array.from({ length: infoRow }, () => ({ hpt: 18 }));
  info.sheet["!margins"] = { left: 0.4, right: 0.4, top: 0.5, bottom: 0.5, header: 0.2, footer: 0.2 };
  XLSX.utils.book_append_sheet(workbook, info.sheet as XLSX.WorkSheet, GL_INFO_SHEET);

  workbook.Workbook = {
    Names: [
      { Name: "_xlnm.Print_Area", Ref: `'${GL_SHEET}'!$A$1:$J$${lastRow}`, Sheet: 0 },
      { Name: "_xlnm.Print_Titles", Ref: `'${GL_SHEET}'!$A$${headerRow}:$J$${headerRow}`, Sheet: 0 },
    ],
  };
  workbook.Props = {
    Title: report.title,
    Subject: "Accounting report",
    Author: "MMH-Connect",
    Comments: "Compact general ledger worksheet with report information on a separate sheet",
    CreatedDate: new Date(),
  };

  return {
    workbook,
    meta: {
      styleMaps: { 0: main.styleMap, 1: info.styleMap },
      printLayout: { headerRow, lastRow, lastTransactionRow },
    },
  };
}

// Excel requires a stable child order in CT_Font and CT_Border; SheetJS does
// not enforce it, but Excel will repair the workbook when the order is wrong.
const font = (size: number, bold: boolean, color?: string) =>
  `<font>${bold ? "<b/>" : ""}<sz val="${size}"/>${color ? `<color rgb="${color}"/>` : ""}<name val="Calibri"/><family val="2"/></font>`;

const side = (name: "left" | "right" | "top" | "bottom", style: string, color: string) =>
  `<${name} style="${style}"><color rgb="${color}"/></${name}>`;

const border = (sides: string) =>
  `<border>${sides}<diagonal/></border>`;

function styleXml() {
  const fonts = [
    font(10, false),
    font(14, true, "FF12372B"),
    font(10, false, "FF5B6B62"),
    font(10, true, "FF1F2937"),
    font(10, true, "FFE8EFEA"),
    font(11, true, "FF12372B"),
    font(10, true, "FFFFFFFF"),
  ];
  const fills = [
    '<fill><patternFill patternType="none"/></fill>',
    '<fill><patternFill patternType="gray125"/></fill>',
    '<fill><patternFill patternType="solid"><fgColor rgb="FF1F4E3D"/><bgColor indexed="64"/></patternFill></fill>',
    '<fill><patternFill patternType="solid"><fgColor rgb="FFF3F6F4"/><bgColor indexed="64"/></patternFill></fill>',
    '<fill><patternFill patternType="solid"><fgColor rgb="FFE8EFEA"/><bgColor indexed="64"/></patternFill></fill>',
    '<fill><patternFill patternType="solid"><fgColor rgb="FFDDE6E0"/><bgColor indexed="64"/></patternFill></fill>',
  ];
  const thin = [
    side("left", "thin", "FFD1D9D4"),
    side("right", "thin", "FFD1D9D4"),
    side("top", "thin", "FFD1D9D4"),
    side("bottom", "thin", "FFD1D9D4"),
  ].join("");
  const borders = [
    border(""),
    border('<bottom style="thin"><color rgb="FFD1D9D4"/></bottom>'),
    border('<top style="medium"><color rgb="FF1F4E3D"/></top>'),
    border(thin),
  ];
  const xfs = STYLE_ORDER.map((key) => {
    const style = STYLES[key];
    const alignment = `<alignment horizontal="${style.align ?? "left"}" vertical="center"${style.wrap ? ' wrapText="1"' : ""}/>`;
    return `<xf numFmtId="${style.format ?? 0}" fontId="${style.font}" fillId="${style.fill}" borderId="${style.border}" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyNumberFormat="1" applyAlignment="1">${alignment}</xf>`;
  });

  return [
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
    `<numFmts count="2"><numFmt numFmtId="${MONEY_FMT_ID}" formatCode="${MONEY_FORMAT}"/><numFmt numFmtId="${DATE_FMT_ID}" formatCode="${DATE_FORMAT}"/></numFmts>`,
    `<fonts count="${fonts.length}">${fonts.join("")}</fonts>`,
    `<fills count="${fills.length}">${fills.join("")}</fills>`,
    `<borders count="${borders.length}">${borders.join("")}</borders>`,
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>',
    `<cellXfs count="${xfs.length}">${xfs.join("")}</cellXfs>`,
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>',
    "</styleSheet>",
  ].join("");
}

function sheetViewXml(headerRow?: number) {
  if (!headerRow) return '<sheetViews><sheetView showGridLines="0" workbookViewId="0"/></sheetViews>';
  const firstDataRow = headerRow + 1;
  return `<sheetViews><sheetView showGridLines="0" workbookViewId="0"><pane ySplit="${headerRow}" topLeftCell="A${firstDataRow}" activePane="bottomLeft" state="frozen"/><selection pane="bottomLeft" activeCell="A${firstDataRow}" sqref="A${firstDataRow}"/></sheetView></sheetViews>`;
}

async function patchWorkbook(bytes: Uint8Array, meta: GLWorkbookMeta) {
  const zip = await JSZip.loadAsync(bytes);
  for (const [sheetIndexText, styleMap] of Object.entries(meta.styleMaps)) {
    const sheetIndex = Number(sheetIndexText);
    const path = `xl/worksheets/sheet${sheetIndex + 1}.xml`;
    const file = zip.file(path);
    if (!file) continue;
    let xml = await file.async("string");
    xml = xml.replace(/<sheetViews>[\s\S]*?<\/sheetViews>/, sheetViewXml(sheetIndex === 0 ? meta.printLayout?.headerRow : undefined));
    if (sheetIndex === 0) {
      xml = xml.replace("<dimension", '<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr><dimension');
    }
    xml = xml.replace(/<c r="([A-Z]+\d+)"([^>]*)>/g, (match, reference: string, attributes: string) => {
      const style = styleMap[reference];
      if (!style) return match;
      const index = STYLE_ORDER.indexOf(style);
      if (index < 0) return match;
      const replaced = /\ss="\d+"/.test(attributes)
        ? attributes.replace(/\ss="\d+"/, ` s="${index}"`)
        : ` s="${index}"${attributes}`;
      return `<c r="${reference}"${replaced}>`;
    });
    if (sheetIndex === 0) {
      if (!xml.includes("<printOptions")) {
        xml = xml.replace("<pageMargins", '<printOptions horizontalCentered="1" gridLines="0" headings="0"/><pageMargins');
      }
      if (!xml.includes("<pageSetup")) {
        xml = xml.replace(/<pageMargins[^>]*\/>/, (match) =>
          `${match}<pageSetup paperSize="9" orientation="landscape" fitToWidth="1" fitToHeight="0"/>`,
        );
      }
      if (!xml.includes("<headerFooter")) {
        xml = xml.replace(/<pageSetup[^>]*\/>/, (match) =>
          `${match}<headerFooter><oddFooter>&amp;CPage &amp;P of &amp;N</oddFooter></headerFooter>`,
        );
      }
    }
    zip.file(path, xml);
  }
  zip.file("xl/styles.xml", styleXml());
  return zip.generateAsync({ type: "uint8array", compression: "DEFLATE" });
}

/** Serialize the configured workbook, including Excel styling and print setup. */
export async function writeGeneralLedgerWorkbook(report: GLExcelReport) {
  const { workbook, meta } = buildGeneralLedgerWorkbook(report);
  const raw = XLSX.write(workbook, {
    bookType: "xlsx",
    type: "array",
    cellDates: true,
    cellStyles: true,
  }) as ArrayBuffer;
  return patchWorkbook(new Uint8Array(raw), meta);
}

/** Download the compact GL workbook from a print preview. */
export async function exportGeneralLedgerWorkbook(report: GLExcelReport, fileName: string) {
  const bytes = await writeGeneralLedgerWorkbook(report);
  const blob = new Blob([bytes as BlobPart], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${fileName}.xlsx`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
