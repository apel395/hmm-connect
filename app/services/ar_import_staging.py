"""Read-only normalization and preflight for historical Catering AR spreadsheets.

This deliberately never creates AR, sales, payments, journals or General Ledger.
Uploaded source rows and validation results are staged separately for review.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
import posixpath
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from typing import Any


CENTS = Decimal("0.01")
ZERO = Decimal("0")
LIMIT = 5000
MONTHS = tuple(range(1, 13))
HARD = frozenset({
    "MISSING_DATE",
    "MISSING_INVOICE_NUMBER",
    "DUPLICATE_NUMBER_IN_FILE",
    "DUPLICATE_EXISTING_AR",
    "DUPLICATE_EXISTING_SALE",
    "INVALID_AMOUNT",
    "DPP_PB1_TOTAL_MISMATCH",
    "AR_TOTAL_MISMATCH",
    "AGING_RECONCILIATION",
    "PRECISION_GT_2_DECIMALS",
    "UNKNOWN_LOCATION",
    "INVALID_CATERING_DIMENSIONS",
    "LOCATION_ACCESS_DENIED",
    "RECEIPT_MISSING_DATE",
})
SITE_CODES = {"RUMIN": "005", "DURI": "006", "LIPET": "010", "DOBS": "014"}


def decimal_value(value: Any) -> Decimal:
    if value is None or value == "":
        return ZERO
    if isinstance(value, bool):
        raise ValueError("Boolean amount is invalid")
    if isinstance(value, (int, float, Decimal)):
        result = Decimal(str(value))
    else:
        raw = str(value).replace("Rp", "").replace(" ", "").strip()
        if "," in raw and "." in raw:
            raw = raw.replace(".", "").replace(",", ".") if raw.rfind(",") > raw.rfind(".") else raw.replace(",", "")
        elif "," in raw:
            a, b = raw.split(",", 1)
            raw = a + "." + b if len(b) < 3 else a + b
        try:
            result = Decimal(raw)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid amount: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"Non-finite amount: {value!r}")
    return result


def source_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (float, int, Decimal)):
        # Modern Excel serial dates (1900 date system) use this epoch.
        return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()
    if isinstance(value, str):
        raw = value.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(raw[:10], fmt).date()
            except ValueError:
                pass
    raise ValueError(f"Invalid date: {value!r}")


def money_string(value: Decimal) -> str:
    return str(value.quantize(CENTS, rounding=ROUND_HALF_UP))


def issue(code: str, details: str = "") -> dict[str, str]:
    return {"code": code, "severity": "BLOCK" if code in HARD else "REVIEW", "message": details or code}


X_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
P_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


class XlsxSheet:
    """Read-only, bounded 45-column sheet with cached formula values."""
    def __init__(self, title: str, rows: dict[int, list]):
        self.title = title
        self.rows = rows

    def iter_rows(self, *, min_row=1, max_row=None, max_col=45, values_only=True):
        if not values_only:
            raise ValueError("Only cell values are supported")
        last = max_row if max_row is not None else max(self.rows, default=0)
        for number in range(min_row, last + 1):
            cells = self.rows.get(number, [])
            yield tuple((cells + [None] * max_col)[:max_col])


class XlsxBook:
    def __init__(self, sheet: XlsxSheet):
        self.worksheets = [sheet]

    def close(self):
        pass


def load_recap_xlsx(content: bytes) -> XlsxBook:
    """Read XLSX XML with the stdlib; Lambda has no openpyxl dependency.

    XLSX is an OOXML ZIP container. Formula cells must supply their cached
    <v> values; the importer never calculates untrusted spreadsheet formulas.
    """
    with ZipFile(BytesIO(content)) as archive:
        paths = set(archive.namelist())
        if "xl/workbook.xml" not in paths or "xl/_rels/workbook.xml.rels" not in paths:
            raise ValueError("Not a valid XLSX workbook")
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = book.find(f"{X_NS}sheets")
        first_sheet = next(iter(sheets), None) if sheets is not None else None
        if first_sheet is None:
            raise ValueError("XLSX has no worksheets")
        sheet_id = first_sheet.attrib.get(f"{R_NS}id")
        sheet_title = first_sheet.attrib.get("name") or "Sheet1"
        relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {r.attrib.get("Id"): r.attrib.get("Target") for r in relations}
        target = targets.get(sheet_id)
        if not target:
            raise ValueError("Missing first worksheet reference")
        sheet_path = (target.lstrip("/") if target.startswith("/") else
                      posixpath.normpath(posixpath.join("xl", target)))
        if sheet_path not in paths or not sheet_path.startswith("xl/worksheets/"):
            raise ValueError("Invalid worksheet path")
        shared = []
        if "xl/sharedStrings.xml" in paths:
            strings = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [
                "".join(t.text or "" for t in item.iter(f"{X_NS}t"))
                for item in strings.findall(f"{X_NS}si")
            ]
        xml = ET.fromstring(archive.read(sheet_path))
        sheet_rows: dict[int, list] = {}
        for r in xml.findall(f".//{X_NS}sheetData/{X_NS}row"):
            row_number = int(r.attrib.get("r") or 0)
            if row_number <= 0:
                continue
            values = [None] * 45
            for cell in r.findall(f"{X_NS}c"):
                ref = cell.attrib.get("r", "")
                match = re.match(r"([A-Z]+)", ref)
                if not match:
                    continue
                column = 0
                for letter in match.group(1):
                    column = column * 26 + (ord(letter) - 64)
                if not 1 <= column <= 45:
                    continue
                kind = cell.attrib.get("t")
                if kind == "inlineStr":
                    inline = cell.find(f"{X_NS}is")
                    value = "".join(t.text or "" for t in inline.iter(f"{X_NS}t")) if inline is not None else None
                else:
                    node = cell.find(f"{X_NS}v")
                    raw = node.text if node is not None else None
                    if raw is None:
                        value = None
                    elif kind == "s":
                        index = int(raw)
                        if index >= len(shared) or index < 0:
                            raise ValueError("Invalid shared string index")
                        value = shared[index]
                    elif kind in ("str", "e"):
                        value = raw
                    elif kind == "b":
                        value = raw == "1"
                    else:
                        try:
                            value = Decimal(raw)
                        except InvalidOperation:
                            value = raw
                values[column - 1] = value
            sheet_rows[row_number] = values
        return XlsxBook(XlsxSheet(sheet_title, sheet_rows))


def parse_catering_workbook(content: bytes) -> list[dict]:
    """Read the actual revenue-recap layout (12 monthly DPP/PB1/TOTAL triplets).

    Do not interpret the month's column as the invoice issue date. Keep the
    invoice date, revenue-period month and source monetary precision separately.
    """
    workbook = load_recap_xlsx(content)
    try:
        sheet = workbook.worksheets[0]
        header_row = None
        for row_number, values in enumerate(sheet.iter_rows(min_row=1, max_row=15, max_col=45, values_only=True), 1):
            if str(values[1] or "").strip().upper() == "LOKASI" and str(values[2] or "").strip().upper() == "TANGGAL INVOICE":
                header_row = row_number
                break
        if header_row is None:
            raise ValueError("Expected revenue recap headers: LOKASI / TANGGAL INVOICE")
        labels = list(next(sheet.iter_rows(min_row=header_row+1, max_row=header_row+1, max_col=45, values_only=True)))
        if any(str(labels[4+(month-1)*3+part] or "").strip().upper() != ("DPP", "PB-1", "TOTAL")[part] for month in MONTHS for part in (0, 1, 2)):
            raise ValueError("Expected 12 monthly DPP / PB-1 / TOTAL groups")
        if str(labels[42] or "").strip().lower() != "jumlah" or str(labels[43] or "").strip().lower() != "sisa aging":
            raise ValueError("Expected Jumlah and Sisa Aging columns")
        rows = []
        for line_number, cells in enumerate(
            sheet.iter_rows(min_row=header_row+3, max_col=45, values_only=True), header_row+3
        ):
            if str(cells[0] or "").strip().upper() in ("TOTAL", "BALANCE"):
                break
            number = str(cells[3] or "").strip()
            if not number and not cells[2] and all(
                value in (None, "", " ", 0)
                for value in cells[4:44]
            ):
                # Some source exports leave the location in an otherwise
                # empty separator row (e.g. 117 and 126). No invoice exists.
                continue
            if not number and not cells[1]:
                continue
            # Missing number with nonzero amounts must remain an exception.
            errors: list[dict] = []
            try:
                invoice_date = source_date(cells[2])
            except ValueError:
                invoice_date = None
                errors.append(issue("MISSING_DATE", f"Invalid invoice date at Excel row {line_number}"))
            if not invoice_date:
                errors.append(issue("MISSING_DATE", "Invoice date is required"))
            if not number:
                errors.append(issue("MISSING_INVOICE_NUMBER", "Invoice number is required"))
            site = str(cells[1] or "").strip().upper()
            if site not in SITE_CODES:
                errors.append(issue("UNKNOWN_LOCATION", f"No approved Catering location mapping for {site!r}"))
            buckets = []
            try:
                for month in MONTHS:
                    start = 4 + (month - 1) * 3
                    dpp, pb1, total = (decimal_value(cells[start+k]) for k in range(3))
                    if any(amount != ZERO for amount in (dpp, pb1, total)):
                        buckets.append({"month": month, "dpp": dpp, "pb1": pb1, "total": total})
                ar = decimal_value(cells[40])
                receipt = decimal_value(cells[42])
                aging = decimal_value(cells[43])
            except ValueError as exc:
                errors.append(issue("INVALID_AMOUNT", str(exc)))
                continue
            try:
                receipt_date = source_date(cells[41])
            except ValueError:
                receipt_date = None
                errors.append(issue("RECEIPT_MISSING_DATE", "Receipt date is invalid"))
            gross = sum((b["total"] for b in buckets), ZERO)
            dpp = sum((b["dpp"] for b in buckets), ZERO)
            pb1 = sum((b["pb1"] for b in buckets), ZERO)
            if gross <= ZERO:
                errors.append(issue("INVALID_AMOUNT", "Gross invoice must be positive"))
            if any(amount < ZERO for amount in (dpp, pb1, gross, ar, receipt, aging)):
                errors.append(issue("INVALID_AMOUNT", "Negative invoice or receipt value"))
            if len(buckets) != 1:
                errors.append(issue("MULTIPLE_REVENUE_MONTHS", f"{len(buckets)} nonzero month buckets; verify source allocation"))
            if abs(dpp + pb1 - gross) > Decimal("0.02"):
                errors.append(issue("DPP_PB1_TOTAL_MISMATCH", f"DPP+PB1 differs from source total by {dpp + pb1 - gross}"))
            if abs(ar - gross) > Decimal("0.02"):
                errors.append(issue("AR_TOTAL_MISMATCH", f"AR differs from monthly totals by {ar - gross}"))
            if abs(ar - receipt - aging) > Decimal("0.02"):
                errors.append(issue("AGING_RECONCILIATION", f"AR - receipt - aging = {ar - receipt - aging}"))
            if any(abs(value - value.quantize(CENTS, rounding=ROUND_HALF_UP)) > Decimal("0.00001") for value in (dpp, pb1, gross, ar, receipt, aging)):
                errors.append(issue("PRECISION_GT_2_DECIMALS", "Source contains more than two decimal places; confirm rounding"))
            if receipt > ZERO and not receipt_date:
                errors.append(issue("RECEIPT_MISSING_DATE", "Receipt amount has no payment date"))
            if receipt > ZERO:
                errors.append(issue("RECEIPT_BANK_RECONCILIATION", "Do not post receipt without bank/GL evidence"))
            if number.upper().endswith("2025"):
                errors.append(issue("NUMBER_YEAR_DIFFERS", "Invoice identifier ends in 2025; preserve original number pending source check"))
            if invoice_date and buckets and buckets[0]["month"] != invoice_date.month:
                errors.append(issue("REVENUE_MONTH_DIFFERS", "Revenue allocation month differs from invoice date"))
            remark = str(cells[44] or "").strip()
            normalized_remark = remark.upper().replace(" ", "")
            estimated_pph = (dpp * Decimal("0.02")).quantize(CENTS, rounding=ROUND_HALF_UP) if receipt > ZERO and "PPH23" in normalized_remark else ZERO
            estimated_pb1 = pb1.quantize(CENTS, rounding=ROUND_HALF_UP) if receipt > ZERO and "PB1" in normalized_remark else ZERO
            if receipt > ZERO and abs(aging-estimated_pph-estimated_pb1) > Decimal("1"):
                errors.append(issue("WITHHOLDING_DIFFERENCE", "Remark-based PPh23/PB1 estimate does not explain remaining aging; verify tax evidence"))
            errors.append(issue("CUSTOMER_MAPPING_REQUIRED", "Source has no legal customer identifier"))
            errors.append(issue("DUE_DATE_REQUIRED", "Source has no contractual due date"))
            errors.append(issue("ACCOUNT_MAPPING_REQUIRED", "AR, revenue and tax accounts need reconciliation with existing GL"))
            rows.append({
                "source_row": line_number,
                "sheet_name": sheet.title,
                "invoice_number": number,
                "location_name": site,
                "location_code": SITE_CODES.get(site),
                "business_unit_code": "002",
                "department_code": "01",
                "invoice_date": invoice_date.isoformat() if invoice_date else None,
                "revenue_month": buckets[0]["month"] if len(buckets) == 1 else None,
                "dpp": str(dpp), "pb1": str(pb1), "gross": str(gross), "ar": str(ar),
                "receipt_date": receipt_date.isoformat() if receipt_date else None,
                "receipt": str(receipt), "aging": str(aging),
                "remark": remark,
                "pph23_estimate": str(estimated_pph),
                "pb1_withheld_estimate": str(estimated_pb1),
                "source_buckets": [{k: (str(v) if isinstance(v, Decimal) else v) for k,v in b.items()} for b in buckets],
                "issues": errors,
            })
            if len(rows) > LIMIT:
                raise ValueError(f"AR import exceeds {LIMIT} invoice rows")
        if not rows:
            raise ValueError("No invoice rows found in revenue recap")
        counts = Counter(row["invoice_number"].strip().casefold() for row in rows if row["invoice_number"])
        for row in rows:
            if row["invoice_number"] and counts[row["invoice_number"].strip().casefold()] > 1:
                row["issues"].append(issue("DUPLICATE_NUMBER_IN_FILE", "The same invoice number appears more than once in this file"))
        return rows
    finally:
        workbook.close()
