"""Prepare or seed April 2026 Project Catering from Kas Harian."""
import argparse
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import re

from seed_catering_january_journals import (
    ACCOUNTS, account, load_source, money, run_db,
)

from seed_catering_march_journals import TAB as MARCH_TAB, counterpart

TAB = "DONE KAS HARIAN APR "
PREFIX = "KH-CATERING-2026-04-"
START, END = date(2026, 4, 1), date(2026, 4, 30)
TOPUPS = {
    307: (184, 295, 116, 119, 50000000),
    600: (310, 583, 102, 118, 80000000),
    1365: (927, 1153, 102, 118, 80000000),
    1383: (1172, 1344, 116, 119, 50000000),
    1839: (1578, 1818, 102, 118, 80000000),
}
PAIRS = (
    (26, 29), (27, 31), (28, 30), (54, 70), (308, 586), (606, 584),
    (613, 634), (704, 726), (705, 727), (707, 739), (711, 730), (778, 783),
    (822, 845), (823, 855), (851, 873), (874, 854), (918, 1167), (919, 1171),
    (922, 1349), (1381, 1168), (1169, 1350), (1444, 1454), (1448, 1455),
    (1474, 1501), (1477, 1502), (1480, 1503), (1492, 1530), (1494, 1577),
    (1496, 1517), (1500, 1504), (1542, 1552), (1842, 1821), (1822, 1826),
    (1825, 1827), (1961, 1986), (2032, 1987), (2033, 1988), (1990, 2048),
    (1993, 2043), (1995, 2049), (2027, 2090), (2003, 2022), (2004, 2023),
)
LOCATIONS = {43: "Batam", 671: "Batam", 848: "Zamped", 849: "Zamped", 1963: "Zamped"}
COUNTERPARTS = {43: "100-210-999", 671: "100-210-999"}


def prepare(source):
    if (source[4][3:7] != ("KETERANGAN", "DEBET", "KREDIT", "SALDO")
            or not str(source[21][3]).startswith("TOTAL SALDO")
            or str(source[2093][3]).strip() != "MUTASI"):
        raise ValueError("April source layout changed")
    opening = {account(r[3].split("(")[-1].split(")")[0]): money(r[4]) for r in source[5:21]}
    closing = {120 if r[4] == "BTN" else account(r[4]): money(r[6]) for r in source[2106:2122]}
    if set(opening) != set(ACCOUNTS) or set(closing) != set(ACCOUNTS):
        raise ValueError("April bank controls changed")

    details = set()
    for receiver, (header, end, sender, recipient, amount) in TOPUPS.items():
        header_row = source[header - 1]
        receipt = source[receiver - 1]
        if (account(header_row[3]) != sender or header_row[0] != receipt[0]
                or money(header_row[4]) or money(header_row[5])
                or account(receipt[3]) != recipient or money(receipt[4]) != amount
                or money(receipt[5])
                or sum(money(r[5]) - money(r[4]) for r in source[header:end]) != amount):
            raise ValueError(f"April petty cash block changed: {header}/{receiver}")
        details.update(range(header + 1, end + 1))

    movements = {}
    for number, row in enumerate(source[23:2093], 24):
        stamp, _, receipt, memo, debit, credit, _ = row
        debit, credit = money(debit), money(credit)
        if number in details or not (debit or credit):
            continue
        keys = {key for key in (account(receipt), account(memo)) if key is not None}
        if number == 2053 and not keys and "ROKAN CAFE" in str(memo) and debit == 5536000:
            keys = {122}
        if (len(keys) != 1 or not isinstance(stamp, datetime) or not START <= stamp.date() <= END
                or min(debit, credit) < 0 or bool(debit) == bool(credit)):
            raise ValueError(f"Invalid April movement at row {number}")
        movements[number] = (number, stamp.date(), str(memo or ""), keys.pop(), debit, credit)

    paired = {}
    consumed = set()
    for outgoing, incoming in PAIRS:
        a, b = movements[outgoing], movements[incoming]
        if ((b[1] - a[1]).days != (1 if outgoing == 1494 else 0) or a[3] == b[3] or a[4] or b[5] or a[5] != b[4]):
            raise ValueError(f"April transfer changed: {outgoing}/{incoming}")
        paired[incoming] = (outgoing, a[3])
        consumed.add(outgoing)
    for incoming, (header, _, sender, _, _) in TOPUPS.items():
        paired[incoming] = (header, sender)

    journals = []
    net = Counter()
    for number, stamp, memo, bank, debit, credit in movements.values():
        if number in consumed:
            continue
        net[bank] += debit - credit
        sender = None
        if number in paired:
            sender, sender_bank = paired[number]
            code = f"100-110-{sender_bank}"
            net[sender_bank] -= debit
        else:
            code = COUNTERPARTS.get(number) or counterpart(memo, debit, credit)
            if debit and re.search(r"TERIMA (?:TAG(?:IHAN)?|BAYAR)\b", memo, re.I):
                code = "100-200-101"
        if code == f"100-110-{bank}":
            raise ValueError(f"Self-posting counterpart at row {number}")
        journals.append((number, stamp, memo, f"100-110-{bank}", debit, credit, code, sender))
    control = {
        f"100-110-{key}": {"opening": opening[key], "net_seed": net[key],
                          "workbook_closing": closing[key],
                          "workbook_minus_seed_closing": closing[key] - opening[key] - net[key]}
        for key in sorted(opening)
    }
    return journals, control


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path, required=True)
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-plan")
    args = parser.parse_args()
    if args.source_only and args.apply:
        parser.error("--source-only and --apply are mutually exclusive")

    source = load_source(args.xlsx, TAB)
    drafts, control = prepare(source)
    march = load_source(args.xlsx, MARCH_TAB)
    prior = {
        f"100-110-{120 if row[4] == 'BTN' else account(row[4])}": money(row[6])
        for row in march[2096:2112]
    }
    if set(prior) != set(control):
        raise ValueError("March closing accounts changed")
    opening_differences = {
        code: item["opening"] - prior[code]
        for code, item in control.items() if item["opening"] != prior[code]
    }
    closing_differences = {
        code: item["workbook_minus_seed_closing"]
        for code, item in control.items() if item["workbook_minus_seed_closing"]
    }
    print(json.dumps({
        "drafts": len(drafts),
        "transfer_journals": sum(row[7] is not None for row in drafts),
        "opening_differences": opening_differences,
        "closing_differences": closing_differences,
        "mapped_counterparts": Counter(row[6] for row in drafts),
    }, indent=2, default=str))
    if args.apply and (opening_differences or closing_differences or not args.expected_plan):
        parser.error("Apply requires reconciled bank controls and the database dry-run plan")
    if not args.source_only:
        run_db(args, drafts, control, source, start=START, end=END, tab=TAB, prefix=PREFIX,
               fees={}, splits={}, location_overrides=LOCATIONS, supporting_details={})


if __name__ == "__main__":
    main()
