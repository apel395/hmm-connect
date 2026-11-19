"""Read-only normalization and preflight for historical Catering AR spreadsheets.

This deliberately never creates AR, sales, payments, journals or General Ledger.
Uploaded source rows and validation results are staged separately for review.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel

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
    if isinstance(value, (float, int)):
        return from_excel(value).date()
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


def parse_catering_workbook(content: bytes) -> list[dict]:
    """Read the actual revenue-recap layout (12 monthly DPP/PB1/TOTAL triplets).

    Do not interpret the month's column as the invoice issue date. Keep the
    invoice date, revenue-period month and source monetary precision separately.
    """
    workbook = load_workbook(BytesIO(content), data_only=True, read_only=True)
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
        if any(str(labels[4+month*3+part] or "").strip().upper() not in ("DPP", "PB-1", "TOTAL")[part:part+1] for month in MONTHS for part in (0, 1, 2)):
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
            if not number and not cells[1]:
                continue
            if not number:
                # A row containing a location but no document number remains
                # an exception to review rather than disappearing silently.
                pass
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
