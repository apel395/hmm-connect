"""Prepare the inferred February bank-interest tax for Project Catering."""
import argparse
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path

from seed_catering_february_journals import TAB
from seed_catering_january_journals import account, load_source, money, run_db
from seed_catering_march_journals import TAB as MARCH_TAB

BANK = "100-110-117"
TAX = "760-100-102"
PREFIX = "KH-CATERING-2026-02-EKI-TAX-"
ROW = 2124


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path)
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-plan")
    args = parser.parse_args()
    if args.apply and (args.source_only or not args.expected_plan):
        parser.error("--apply requires --expected-plan from the database dry-run")

    february = load_source(args.xlsx, TAB)
    march = load_source(args.xlsx, MARCH_TAB)
    stamp, _, _, memo, debit, credit, _ = february[ROW - 1]
    feb_close = february[2167]
    mar_open = march[12]
    if (
        stamp != datetime(2026, 2, 28)
        or account(memo) != 117 or "BUNGA" not in memo.upper()
        or money(debit) != Decimal("825.20") or money(credit)
        or account(feb_close[4]) != 117 or account(mar_open[3].split("(")[-1].split(")")[0]) != 117
        or mar_open[0] != datetime(2026, 3, 1)
    ):
        raise ValueError("February interest or balance source changed")
    closing, opening = money(feb_close[6]), money(mar_open[4])
    amount = (money(debit) * Decimal("0.20")).quantize(Decimal("0.01"))
    if closing - opening != amount or amount != Decimal("165.04"):
        raise ValueError("Opening difference no longer matches the inferred tax")

    control = {BANK: {
        "february_workbook_closing": closing,
        "net_correction": -amount,
        "corrected_february_closing": closing - amount,
        "march_workbook_opening": opening,
    }}
    print(json.dumps({
        "reference": f"{PREFIX}{ROW}",
        "basis": "Inferred from February interest and March opening balance",
        "debit_coa": TAX, "credit_coa": BANK, "amount": amount,
        "bank_control": control,
    }, default=str, indent=2))
    if args.source_only:
        return

    description = (
        "Koreksi pajak bunga Mandiri Eki - inferensi 20% bunga Februari "
        "baris 2124, cocok dengan selisih saldo awal Maret"
    )
    drafts = [(ROW, stamp.date(), description, BANK, Decimal(0), amount, TAX, None)]
    run_db(
        args, drafts, control, february, start=date(2026, 2, 1), end=stamp.date(),
        tab=TAB, prefix=PREFIX, fees={}, splits={}, location_overrides={ROW: "Batam"},
        supporting_details={},
    )


if __name__ == "__main__":
    main()
