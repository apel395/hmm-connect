"""Seed May 2026 Project Catering drafts from the Kas Harian workbook."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from audit_catering_may_journals import END, START, TAB, TOPUPS, prepare
from seed_catering_april_journals import TAB as APRIL_TAB
from seed_catering_january_journals import URL, account, load_source, money, run_db

PREFIX = "KH-CATERING-2026-05-"
ROUNDING = {
    "100-110-102": Decimal("0.32"),
    "100-110-120": Decimal("-0.32"),
}


def prepare_month(workbook):
    source = load_source(workbook, TAB)
    april = load_source(workbook, APRIL_TAB)
    drafts, control = prepare(source)
    prior = {
        f"100-110-{120 if row[4] == 'BTN' else account(row[4])}": money(row[6])
        for row in april[2106:2122]
    }
    if set(prior) != set(control):
        raise ValueError("April closing account set changed")
    opening_differences = {
        code: item["opening"] - prior[code]
        for code, item in control.items() if item["opening"] != prior[code]
    }
    block_differences = {
        header: total - amount
        for _, (header, end, _, _, amount) in TOPUPS.items()
        if (total := sum(money(row[5]) - money(row[4]) for row in source[header:end])) != amount
    }
    closing_differences = {
        code: item["workbook_minus_seed_closing"]
        for code, item in control.items() if item["workbook_minus_seed_closing"]
    }
    ignored_rounding = {
        code: difference for code, difference in closing_differences.items()
        if ROUNDING.get(code) == difference
    }
    remaining_closing = {
        code: difference for code, difference in closing_differences.items()
        if code not in ignored_rounding
    }
    unresolved = [row[0] for row in drafts if row[6] is None]
    report = {
        "source_controls_pass": not (
            opening_differences or block_differences or remaining_closing or unresolved
        ),
        "drafts": len(drafts),
        "transfer_journals": sum(row[7] is not None for row in drafts),
        "opening_differences": opening_differences,
        "petty_cash_detail_minus_topup": block_differences,
        "closing_differences": remaining_closing,
        "ignored_bank_rounding": ignored_rounding,
        "unresolved_counterpart_rows": unresolved,
        "mapped_counterparts": dict(Counter(row[6] for row in drafts)),
    }
    # Preserve raw source differences in the database plan and activity fingerprint.
    for code, difference in ignored_rounding.items():
        control[code]["ignored_rounding"] = difference
    return source, drafts, control, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path, help="Use a local XLSX instead of Google Sheets")
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--expected-plan")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply and args.source_only:
        parser.error("--source-only and --apply are mutually exclusive")

    if args.xlsx is None:
        with TemporaryDirectory(prefix="kas-harian-may-") as directory:
            workbook = Path(directory) / "kas-harian.xlsx"
            with urlopen(URL, timeout=60) as response:
                workbook.write_bytes(response.read())
            source, drafts, control, report = prepare_month(workbook)
    else:
        source, drafts, control, report = prepare_month(args.xlsx)
    print(json.dumps(report, indent=2, default=str))
    if not report["source_controls_pass"]:
        parser.error("May source controls changed. See the differences above.")
    if not args.source_only:
        run_db(
            args, drafts, control, source, start=START, end=END, tab=TAB, prefix=PREFIX,
            fees={}, splits={}, location_overrides={}, supporting_details={},
        )


if __name__ == "__main__":
    main()
