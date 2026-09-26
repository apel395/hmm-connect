#!/usr/bin/env python3
"""Seed the two corrected HULU CAFÉ historical invoices without an XLSX file.

The corrected source values are hard-coded from the reviewed workbook:
- source row 750: subtotal 500,000 + tax 50,000 = invoice 550,000
- source row 752: subtotal 2,537,000 + tax 253,700 = invoice 2,790,700

This script generates a temporary workbook with the original source row numbers,
then delegates to the canonical RESIPING historical seeder so GR/SI/journal logic
stays identical to the previously applied batches.

Dry-run is the default. Use --apply only after reviewing the printed control.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

ROW750_ITEMS = [
    (751, None, "ICE MILK COFFEE 250ML", "BTL", Decimal("20"), Decimal("25000")),
]

ROW752_ITEMS = [
    (753, "RAWON IGA", "RAWON IGA", "PORSI", Decimal("2"), Decimal("55000")),
    (754, "AYAM TALIWANG", "AYAM TALIWANG", "PORSI", Decimal("2"), Decimal("45000")),
    (755, "TONGSENG AYAM", "TONGSENG AYAM", "PORSI", Decimal("1"), Decimal("40000")),
    (756, "PISANG KIPAS", "PISANG KIPAS", "PORSI", Decimal("2"), Decimal("20000")),
    (757, "UBI GORENG", "UBI GORENG", "PORSI", Decimal("1"), Decimal("15000")),
    (758, "ICE AMERICACO", "ICE AMERICACO", "PORSI", Decimal("2"), Decimal("20000")),
    (759, "HOT AMERICANO", "HOT AMERICANO", "PORSI", Decimal("1"), Decimal("20000")),
    (760, "ICE MILK COFFEE", "ICE MILK COFFEE", "PORSI", Decimal("1"), Decimal("22000")),
    (761, "ICE LYCHEE TEA", "ICE LYCHEE TEA", "PORSI", Decimal("2"), Decimal("22000")),
    (762, "BLACKMOON", "BLACKMOON", "PORSI", Decimal("1"), Decimal("35000")),
    (763, "BLACKMOON", "BLACKMOON", "PORSI", Decimal("2"), Decimal("35000")),
    (764, "ICE LYCHEE TEA", "ICE LYCHEE TEA", "PORSI", Decimal("1"), Decimal("22000")),
    (765, "HOT LICHEE TEA", "HOT LICHEE TEA", "PORSI", Decimal("1"), Decimal("22000")),
    (766, "SALTED CARAMELLATE", "SALTED CARAMELLATE", "PORSI", Decimal("2"), Decimal("30000")),
    (767, "HOT CHOCO CREAM CHEESE", "HOT CHOCO CREAM CHEESE", "PORSI", Decimal("2"), Decimal("30000")),
    (768, "MATCHA CREAM CHESEE", "MATCHA CREAM CHESEE", "PORSI", Decimal("1"), Decimal("35000")),
    (769, "TARO CREAM CHEESE", "TARO CREAM CHEESE", "PORSI", Decimal("3"), Decimal("30000")),
    (770, "ICE HULU MOCHA", "ICE HULU MOCHA", "PORSI", Decimal("2"), Decimal("32000")),
    (771, "HOT HULU MOCHA", "HOT HULU MOCHA", "PORSI", Decimal("1"), Decimal("32000")),
    (772, "CLOUDY BUTTER LATTE", "CLOUDY BUTTER LATTE", "PORSI", Decimal("1"), Decimal("30000")),
    (773, "THAI TEA", "THAI TEA", "PORSI", Decimal("1"), Decimal("20000")),
    (774, "HOT LATTE", "HOT LATTE", "PORSI", Decimal("1"), Decimal("25000")),
    (775, "HOT CAPPUCINO", "HOT CAPPUCINO", "PORSI", Decimal("2"), Decimal("25000")),
    (776, "HOT AMERICANO", "HOT AMERICANO", "PORSI", Decimal("1"), Decimal("20000")),
    (777, "MAGIC", "MAGIC", "PORSI", Decimal("1"), Decimal("27000")),
    (778, "COUGH REMEDY", "COUGH REMEDY", "PORSI", Decimal("2"), Decimal("20000")),
    (779, "MINERAL WATER", "MINERAL WATER", "PORSI", Decimal("1"), Decimal("8000")),
    (780, "CHOCO FORREST", "CHOCO FORREST", "PORSI", Decimal("1"), Decimal("30000")),
    (781, "CHOCO CHEESE TOAST", "CHOCO CHEESE TOAST", "PORSI", Decimal("2"), Decimal("25000")),
    (782, "TEMPE MENDOAN", "TEMPE MENDOAN", "PORSI", Decimal("5"), Decimal("18000")),
    (783, "UBI GORENG", "UBI GORENG", "PORSI", Decimal("5"), Decimal("15000")),
    (784, "FRENCH FRIES", "FRENCH FRIES", "PORSI", Decimal("2"), Decimal("20000")),
    (785, "PISANG KIPAS", "PISANG KIPAS", "PORSI", Decimal("3"), Decimal("20000")),
    (786, "CHICKEN POPCORN", "CHICKEN POPCORN", "PORSI", Decimal("1"), Decimal("25000")),
    (787, "SPRING ROLL", "SPRING ROLL", "PORSI", Decimal("1"), Decimal("18000")),
    (788, "PASTEL MINI", "PASTEL MINI", "PORSI", Decimal("1"), Decimal("18000")),
    (789, "ICE MILK COFFE 250ML", "ICE MILK COFFE 250ML", "BTL", Decimal("40"), Decimal("25000")),
]


def validate_hardcoded_source() -> None:
    subtotal_750 = sum(qty * price for _, _, _, _, qty, price in ROW750_ITEMS)
    subtotal_752 = sum(qty * price for _, _, _, _, qty, price in ROW752_ITEMS)

    if subtotal_750 != Decimal("500000"):
        raise RuntimeError(f"row 750 hardcoded subtotal mismatch: {subtotal_750}")
    if subtotal_750 + Decimal("50000") != Decimal("550000"):
        raise RuntimeError("row 750 hardcoded invoice mismatch")

    if subtotal_752 != Decimal("2537000"):
        raise RuntimeError(f"row 752 hardcoded subtotal mismatch: {subtotal_752}")
    if subtotal_752 + Decimal("253700") != Decimal("2790700"):
        raise RuntimeError("row 752 hardcoded invoice mismatch")

    print("HARDCODED SOURCE VALIDATION: OK")
    print("  row 750 HULU CAFÉ: subtotal=500000 tax=50000 invoice=550000")
    print("  row 752 HULU CAFÉ: subtotal=2537000 tax=253700 invoice=2790700")


def build_temp_workbook(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    ws.append([
        "tanggal penerimaan", "nama supplier", "lokasi", "nama barang",
        "deskripsi", "satuan", "jumlah diterima", "harga satuan",
        "tanggal invoice/tagihan", "", "pajak", "total", "TOTAL INVOICE",
    ])

    # Keep original source row numbers so canonical historical invoice numbers,
    # references, and audit notes stay aligned with the reviewed workbook.
    for row_no in range(2, 790):
        if row_no == 750:
            ws.cell(row_no, 1, datetime(2025, 12, 18))
            ws.cell(row_no, 2, "HULU CAFÉ")
            ws.cell(row_no, 3, "RUMBAI")
            ws.cell(row_no, 4, "FOOD")
            ws.cell(row_no, 13, 550000)
            continue

        if row_no == 751:
            _, _, description, uom, qty, price = ROW750_ITEMS[0]
            ws.cell(row_no, 5, description)
            ws.cell(row_no, 6, uom)
            ws.cell(row_no, 7, float(qty))
            ws.cell(row_no, 8, float(price))
            ws.cell(row_no, 11, 50000)
            ws.cell(row_no, 12, 500000)
            continue

        if row_no == 752:
            ws.cell(row_no, 1, "10-12 DES 25")
            ws.cell(row_no, 2, "HULU CAFÉ")
            ws.cell(row_no, 3, "RUMBAI")
            ws.cell(row_no, 4, "FOOD")
            ws.cell(row_no, 13, 2790700)
            continue

    for row_no, name, description, uom, qty, price in ROW752_ITEMS:
        ws.cell(row_no, 5, description or name)
        ws.cell(row_no, 6, uom)
        ws.cell(row_no, 7, float(qty))
        ws.cell(row_no, 8, float(price))

    ws.cell(789, 11, 253700)
    ws.cell(789, 12, 2790700)

    wb.save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="admin")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    validate_hardcoded_source()

    scripts_dir = Path(__file__).resolve().parent
    preferred = scripts_dir / "seed_resiping_historical_v2.py"
    canonical = scripts_dir / "seed_resiping_historical.py"
    base_script = preferred if preferred.exists() else canonical
    if not base_script.exists():
        raise RuntimeError(
            "Base seeder not found. Expected scripts/seed_resiping_historical_v2.py "
            "or scripts/seed_resiping_historical.py"
        )

    with tempfile.TemporaryDirectory(prefix="resiping-fixed-hulu-") as temp_dir:
        workbook = Path(temp_dir) / "RESIPING_HULU_FIXED.xlsx"
        build_temp_workbook(workbook)

        command = [
            sys.executable,
            str(base_script),
            "--workbook",
            str(workbook),
            "--user",
            args.user,
            "--start-row",
            "750",
            "--only-invoice-rows",
            "750,752",
        ]
        if args.apply:
            command.append("--apply")

        print("RUNNING:", " ".join(command))
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
