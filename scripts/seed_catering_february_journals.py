"""Prepare or seed February 2026 Project Catering from Kas Harian."""
import argparse
from collections import Counter
from datetime import date, datetime
import json
from pathlib import Path
import re

from seed_catering_january_journals import (
    ACCOUNTS, SALES_RECEIPT, account, expense_counterpart, load_source, money, run_db,
)

TAB = "DONE KAS HARIAN FEB"
PREFIX = "KH-CATERING-2026-02-"
START, END = date(2026, 2, 1), date(2026, 2, 28)
TOPUPS = {
    466: (162, 446, 102, 118, 79600000),
    751: (696, 736, 116, 119, 50000000),
    1020: (756, 1009, 102, 118, 78240000),
    1514: (1216, 1491, 102, 118, 80000000),
    1661: (1585, 1641, 116, 119, 50000000),
    2125: (1833, 2081, 102, 118, 80000000),
}
PAIRS = (
    (37, 43), (41, 48), (451, 447), (453, 454), (1119, 1121), (1120, 1128),
    (1155, 1156), (1178, 1194), (1179, 1195), (1668, 1678), (1670, 1696),
    (1762, 1805), (1764, 1795), (1765, 1806), (1770, 1790), (1771, 1799),
    (1773, 1791), (1800, 1760), (2085, 1830),
)
LOCATIONS = {500: "Gemsmart Duri", 682: "Hulu Cafe", 1775: "Pekanbaru"}


def counterpart(number, memo, debit, credit):
    memo = memo.upper()
    if debit:
        if number in {2114, 2116}:
            return "700-500-122" if number == 2114 else "760-100-102"
        if re.search(SALES_RECEIPT + r"|PENJUALAN|MESIN|\bSALES\b|TERIMA PEMBAYARAN CATERING", memo) or number in {
            147, 151, 504, 614, 616, 677, 1752,
        }:
            return "100-200-101"
        if re.search(r"TERIMA\s+KMK", memo):
            return "200-300-104"
        if re.search(r"BUNGA|JASA GIRO", memo):
            return "760-100-100"
        if re.search(r"CLOSING|REFUND|PENGEMBALIAN KASBON", memo):
            return "200-200-100" if "PAYROLL" in memo else "100-210-999"
        if number == 44:
            return "200-200-100"
        if re.search(r"DEPOSIT|DP RESERVASI", memo):
            return "200-300-106"
        return "200-300-999"

    for pattern, code in (
        (r"FASILITAS\s+BUNGA.*KMK|BIAYA BUNGA", "760-100-103"),
        (r"PELUNASAN\s+KMK|ANGSURAN\s+BAKI\s+DEBIT\s+KMK", "200-300-104"),
        (r"ANGSURAN.*(?:KMK|KPBA)", "200-300-999"),
        (r"ANGSURAN.*(?:HIACE|LEASING)", "200-700-105"),
        (r"CASH ADVANCE|CLOSING|\bKASBON\b", "100-210-999"),
        (r"BPJS\s+(?:KES|KESEHATAN)", "200-200-112"),
        (r"BPJS\s+(?:TK|KETENAGAKERJAAN)", "200-200-113"),
        (r"\bPB1\b|\bPBJT\b", "200-400-100"),
        (r"\bPPH\s*(?:FINAL|4)\b", "200-400-105"),
        (r"\bPPH\s*21\b", "200-400-102"),
        (r"\bPPH\s*23\b", "200-400-103"),
        (r"\bPPH\s*25\b", "200-400-104"),
        (r"\bPAYROLL\b|\bBAYAR GAJI\b", "200-200-100"),
        (r"\bPAJAK(?:\s+\d+)?\s*$", "760-100-102"),
        (r"\bZIS\b", "700-500-127"),
    ):
        if re.search(pattern, memo):
            return code
    expense = expense_counterpart(memo)
    if expense or re.search(r"\b(?:INV(?:OICE)?|TAGIHAN)\b", memo) or credit >= 1_000_000:
        return expense or "200-100-1"
    return "700-500-999"


def prepare(source):
    if (source[4][3:7] != ("KETERANGAN", "DEBET", "KREDIT", "SALDO")
            or not str(source[21][3]).startswith("TOTAL SALDO")
            or str(source[2147][3]).strip() != "MUTASI"):
        raise ValueError("February source layout changed")
    opening = {account(r[3].split("(")[-1].split(")")[0]): money(r[4]) for r in source[5:21]}
    closing = {120 if r[4] == "BTN" else account(r[4]): money(r[6]) for r in source[2160:2176]}
    if set(opening) != set(ACCOUNTS) or set(closing) != set(ACCOUNTS):
        raise ValueError("February bank controls changed")

    details = set()
    for receiver, (header, end, sender, recipient, amount) in TOPUPS.items():
        header_row = source[header - 1]
        receipt = source[receiver - 1]
        if (account(header_row[3]) != sender or header_row[0] != receipt[0]
                or money(header_row[4]) or money(header_row[5])
                or account(receipt[3]) != recipient or money(receipt[4]) != amount
                or money(receipt[5])
                or sum(money(r[5]) - money(r[4]) for r in source[header:end]) != amount):
            raise ValueError(f"February petty cash block changed: {header}/{receiver}")
        details.update(range(header + 1, end + 1))

    movements = {}
    for number, row in enumerate(source[23:2147], 24):
        stamp, _, receipt, memo, debit, credit, _ = row
        debit, credit = money(debit), money(credit)
        if number in details or not (debit or credit):
            continue
        keys = {key for key in (account(receipt), account(memo)) if key is not None}
        if (len(keys) != 1 or not isinstance(stamp, datetime) or not START <= stamp.date() <= END
                or min(debit, credit) < 0 or bool(debit) == bool(credit)):
            raise ValueError(f"Invalid February movement at row {number}")
        movements[number] = (number, stamp.date(), str(memo or ""), keys.pop(), debit, credit)

    paired = {}
    consumed = set()
    for outgoing, incoming in PAIRS:
        a, b = movements[outgoing], movements[incoming]
        if (a[1] != b[1] or a[3] == b[3] or a[4] or b[5] or a[5] != b[4]
                or not re.search(r"PINDAH DANA", a[2], re.I)
                or not re.search(r"TERIMA (?:PINDAH )?DANA\s*DARI", b[2], re.I)):
            raise ValueError(f"February transfer changed: {outgoing}/{incoming}")
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
            code = counterpart(number, memo, debit, credit)
        if code == f"100-110-{bank}":
            raise ValueError(f"Self-posting bank counterpart at row {number}")
        journals.append((number, stamp, memo, f"100-110-{bank}", debit, credit, code, sender))
    control = {
        f"100-110-{key}": {"opening": opening[key], "net_seed": net[key],
                          "workbook_closing": closing[key],
                          "workbook_minus_seed_closing": closing[key] - opening[key] - net[key]}
        for key in sorted(opening)
    }
    if any(item["workbook_minus_seed_closing"] for item in control.values()):
        raise ValueError(f"February bank controls do not reconcile: {control}")
    return journals, control


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path)
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--expected-plan")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.source_only and args.apply:
        parser.error("--source-only and --apply are mutually exclusive")
    source = load_source(args.xlsx, TAB)
    drafts, control = prepare(source)
    if args.source_only:
        print(json.dumps({"drafts": len(drafts), "transfer_journals": sum(r[7] is not None for r in drafts),
                          "mapped_counterparts": Counter(r[6] for r in drafts),
                          "bank_control": control}, indent=2, default=str))
    else:
        run_db(args, drafts, control, source, start=START, end=END, tab=TAB, prefix=PREFIX,
               fees={}, splits={}, location_overrides=LOCATIONS, supporting_details={})


if __name__ == "__main__":
    main()
