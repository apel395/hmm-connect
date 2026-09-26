#!/usr/bin/env python3
"""Seed only the corrected RESIPING blocked invoices from 2025-12.

This wrapper intentionally processes only the two source-proven HULU CAFÉ
invoice groups that were corrected by the data inputer:

- row 750: subtotal 500,000 + tax 50,000 = TOTAL INVOICE 550,000
- row 752: subtotal 2,537,000 + tax 253,700 = TOTAL INVOICE 2,790,700

Rows 567 (SLAMET SUPRIYANTO), 607 (PUGUH WIBOWO), and 744 (KHAS MELAYU)
remain excluded because their item-level arithmetic still does not reconcile
to the corrected invoice/block totals.

Dry-run is the default. Pass --apply only after the validation printed by this
script succeeds.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook

ZERO = Decimal("0")
FIXED_INVOICE_ROWS = (750, 752)


def dec(value):
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    raw = str(value).strip().replace(" ", "")
    if re.fullmatch(r"-?\d+,\d{1,2}", raw):
        raw = raw.replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(?:,\d{3})+,\d{1,2}", raw):
        left, right = raw.rsplit(",", 1)
        raw = left.replace(",", "") + "." + right
    elif re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+\.\d{1,2}", raw):
        left, right = raw.rsplit(".", 1)
        raw = left.replace(".", "") + "." + right
    else:
        raw = raw.replace(",", "")
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def tax_dec(value):
    amount = dec(value)
    if amount is None:
        return ZERO
    raw = str(value or "").strip()
    if amount > ZERO and amount < Decimal("1000"):
        if "." in raw or amount == amount.to_integral():
            return (amount * Decimal("1000")).quantize(Decimal("1"))
    return amount


def require_equal(label: str, actual: Decimal | None, expected: Decimal) -> None:
    if actual != expected:
        raise RuntimeError(
            f"{label}: expected {expected}, found {actual}. "
            "Refusing to seed because the workbook is not the corrected source."
        )


def validate_corrected_hulu(workbook: Path) -> None:
    wb = load_workbook(workbook, read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]

        # Row 750: corrected missing PPN.
        require_equal("row 750 TOTAL INVOICE", dec(ws["M750"].value), Decimal("550000"))
        require_equal("row 751 quantity", dec(ws["G751"].value), Decimal("20"))
        require_equal("row 751 unit price", dec(ws["H751"].value), Decimal("25000"))
        require_equal("row 751 source subtotal", dec(ws["L751"].value), Decimal("500000"))
        require_equal("row 751 tax", tax_dec(ws["K751"].value), Decimal("50000"))
        subtotal_750 = dec(ws["G751"].value) * dec(ws["H751"].value)
        require_equal("row 750 calculated subtotal", subtotal_750, Decimal("500000"))
        require_equal(
            "row 750 calculated invoice",
            subtotal_750 + tax_dec(ws["K751"].value),
            Decimal("550000"),
        )

        # Row 752: corrected detail now reconciles to subtotal 2,537,000.
        require_equal("row 752 TOTAL INVOICE", dec(ws["M752"].value), Decimal("2790700"))
        subtotal_752 = ZERO
        for row in range(753, 790):
            qty = dec(ws[f"G{row}"].value)
            price = dec(ws[f"H{row}"].value)
            if qty is None or price is None:
                raise RuntimeError(
                    f"row {row}: missing/unparseable quantity or price inside corrected "
                    "HULU CAFÉ invoice row 752."
                )
            subtotal_752 += qty * price

        require_equal("row 752 calculated subtotal", subtotal_752, Decimal("2537000"))
        require_equal("row 789 tax", tax_dec(ws["K789"].value), Decimal("253700"))
        require_equal("row 789 declared total", dec(ws["L789"].value), Decimal("2790700"))
        require_equal(
            "row 752 calculated invoice",
            subtotal_752 + tax_dec(ws["K789"].value),
            Decimal("2790700"),
        )
    finally:
        wb.close()

    print("SOURCE VALIDATION: OK")
    print("  row 750 HULU CAFÉ: 500,000 + 50,000 tax = 550,000")
    print("  row 752 HULU CAFÉ: 2,537,000 + 253,700 tax = 2,790,700")
    print("  excluded unresolved rows: 567, 607, 744")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", required=True)
    parser.add_argument("--user", default="admin")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    workbook = Path(args.workbook).resolve()
    if not workbook.exists():
        raise RuntimeError(f"Workbook not found: {workbook}")

    validate_corrected_hulu(workbook)

    scripts_dir = Path(__file__).resolve().parent
    preferred = scripts_dir / "seed_resiping_historical_v2.py"
    canonical = scripts_dir / "seed_resiping_historical.py"
    base_script = preferred if preferred.exists() else canonical
    if not base_script.exists():
        raise RuntimeError(
            "Base seeder not found. Expected scripts/seed_resiping_historical_v2.py "
            "or scripts/seed_resiping_historical.py"
        )

    command = [
        sys.executable,
        str(base_script),
        "--workbook",
        str(workbook),
        "--user",
        args.user,
        "--start-row",
        "567",
        "--only-invoice-rows",
        ",".join(str(row) for row in FIXED_INVOICE_ROWS),
    ]
    if args.apply:
        command.append("--apply")

    print("RUNNING:", " ".join(command))
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
