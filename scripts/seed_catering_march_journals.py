"""Prepare or seed March 2026 Project Catering from Kas Harian."""
import argparse
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import re

from seed_catering_january_journals import (
    ACCOUNTS, SALES_RECEIPT, account, expense_counterpart, load_source, money, run_db,
)

from seed_catering_february_journals import TAB as FEBRUARY_TAB

TAB = "DONE KAS HARIAN MAR"
PREFIX = "KH-CATERING-2026-03-"
START, END = date(2026, 3, 1), date(2026, 3, 31)
TOPUPS = {
    358: (219, 325, 116, 117, 20000000),
    674: (419, 666, 102, 118, 80000000),
    1238: (884, 1192, 102, 118, 80000000),
    1239: (1197, 1230, 116, 119, 50000000),
    1729: (1405, 1707, 102, 118, 80000000),
    2065: (1939, 2002, 116, 119, 50000000),
}
PAIRS = (
    (33,49), (35,50), (37,51), (72,38), (44,52), (79,116), (113,140),
    (145,141), (149,162), (159,169), (194,214), (195,336), (197,337),
    (199,338), (201,339), (359,331), (685,689), (709,688), (755,777),
    (828,825), (1348,1295), (1359,1369), (1790,1799), (1791,1800),
    (1792,1801), (1795,1798), (1811,1797), (1840,1823), (1843,1824),
    (1845,1825), (1846,1826), (1829,1864), (1831,1856), (1900,1913),
    (1905,1910), (1906,1915), (1908,1914), (2022,1926),
)
FAILED_TRANSFERS = ((1852, 1848), (1855, 1850))
LOCATIONS = {}
SPLIT = {"1316-RUMIN": Decimal("37000000"), "1316-DIR": Decimal("50000000")}


def counterpart(memo, debit, credit):
    memo = memo.upper()
    if debit:
        if "REFUND BIAYA ADM" in memo:
            return "700-500-122"
        if re.search(SALES_RECEIPT + r"|PENJUALAN|MESIN|\bSALES\b|TERIMA PEMBAYARAN CATERING", memo):
            return "100-200-101"
        if re.search(r"TERIMA\s+KMK", memo):
            return "200-300-104"
        if re.search(r"BUNGA|JASA GIRO", memo):
            return "760-100-100"
        if re.search(r"CLOSING|REFUND|PENGEMBALIAN KASBON", memo):
            return "200-200-100" if "PAYROLL" in memo else "100-210-999"
        if "PENGEMBALIAN PAYROLL" in memo:
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
    if re.search(r"\b(?:INV(?:OICE)?|TAGIHAN)\b", memo):
        return "200-100-1"
    expense = expense_counterpart(memo)
    return expense or ("200-100-1" if credit >= 1_000_000 else "700-500-999")


def prepare(source):
    if (source[4][3:7] != ("KETERANGAN", "DEBET", "KREDIT", "SALDO")
            or not str(source[21][3]).startswith("TOTAL SALDO")
            or str(source[2083][3]).strip() != "MUTASI"):
        raise ValueError("March source layout changed")
    opening = {account(r[3].split("(")[-1].split(")")[0]): money(r[4]) for r in source[5:21]}
    closing = {120 if r[4] == "BTN" else account(r[4]): money(r[6]) for r in source[2096:2112]}
    if set(opening) != set(ACCOUNTS) or set(closing) != set(ACCOUNTS):
        raise ValueError("March bank controls changed")

    details = set()
    for receiver, (header, end, sender, recipient, amount) in TOPUPS.items():
        header_row = source[header - 1]
        receipt = source[receiver - 1]
        if (account(header_row[3]) != sender or header_row[0] != receipt[0]
                or money(header_row[4]) or money(header_row[5])
                or account(receipt[3]) != recipient or money(receipt[4]) != amount
                or money(receipt[5])
                or sum(money(r[5]) - money(r[4]) for r in source[header:end]) != amount):
            raise ValueError(f"March petty cash block changed: {header}/{receiver}")
        details.update(range(header + 1, end + 1))

    movements = {}
    for number, row in enumerate(source[23:2083], 24):
        stamp, _, receipt, memo, debit, credit, _ = row
        debit, credit = money(debit), money(credit)
        if number in details or not (debit or credit):
            continue
        keys = {key for key in (account(receipt), account(memo)) if key is not None}
        if number == 1316 and not keys and "JD257238" in str(memo) and credit == sum(SPLIT.values()):
            keys = {102}
        if (len(keys) != 1 or not isinstance(stamp, datetime) or not START <= stamp.date() <= END
                or min(debit, credit) < 0 or bool(debit) == bool(credit)):
            raise ValueError(f"Invalid March movement at row {number}")
        movements[number] = (number, stamp.date(), str(memo or ""), keys.pop(), debit, credit)

    paired = {}
    consumed = set()
    for outgoing, incoming in FAILED_TRANSFERS:
        a, b = movements[outgoing], movements[incoming]
        if a[1] != b[1] or a[3] != b[3] or a[4] or b[5] or a[5] != b[4] or "TRANSAKSI GAGAL" not in b[2]:
            raise ValueError("Failed BSI transfer control changed")
        consumed.update((outgoing, incoming))
    for outgoing, incoming in PAIRS:
        a, b = movements[outgoing], movements[incoming]
        if (a[1] != b[1] or a[3] == b[3] or a[4] or b[5] or a[5] != b[4]):
            raise ValueError(f"March transfer changed: {outgoing}/{incoming}")
        paired[incoming] = (outgoing, a[3])
        consumed.add(outgoing)
    for incoming, (header, _, sender, _, _) in TOPUPS.items():
        paired[incoming] = (header, sender)

    # The CSR receipt has no verified counterpart in the bank movements.
    csr = movements[2052]
    if csr[3:6] != (117, Decimal("5155000"), 0) or "CSR PROJECT" not in csr[2]:
        raise ValueError("CSR receipt evidence changed")
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
        elif number == 2052:
            code = None
        else:
            code = counterpart(memo, debit, credit)
        if code == f"100-110-{bank}":
            raise ValueError(f"Self-posting bank counterpart at row {number}")
        if number == 1316:
            for ref, amount in SPLIT.items():
                split_code = "200-100-1" if ref.endswith("RUMIN") else "100-210-999"
                label = "Bahan baku makanan Rumin" if ref.endswith("RUMIN") else "Dana darurat direksi"
                journals.append((ref, stamp, label + " | " + memo, f"100-110-{bank}", 0, amount, split_code, None))
        else:
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
    parser.add_argument("--xlsx", type=Path)
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--expected-plan")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.source_only and args.apply:
        parser.error("--source-only and --apply are mutually exclusive")
    source = load_source(args.xlsx, TAB)
    drafts, control = prepare(source)
    february = load_source(args.xlsx, FEBRUARY_TAB)
    prior_closing = {
        f"100-110-{120 if row[4] == 'BTN' else account(row[4])}": money(row[6])
        for row in february[2160:2176]
    }
    if set(prior_closing) != set(control):
        raise ValueError("February closing accounts changed")
    opening_differences = {
        code: item["opening"] - prior_closing[code]
        for code, item in control.items() if item["opening"] != prior_closing[code]
    }
    closing_differences = {
        code: item["workbook_minus_seed_closing"]
        for code, item in control.items() if item["workbook_minus_seed_closing"]
    }
    unresolved = [r[0] for r in drafts if r[6] is None]
    blocked = bool(opening_differences or closing_differences or unresolved)
    print(json.dumps({
        "ready_to_apply": not blocked,
        "drafts": len(drafts),
        "transfer_journals": sum(r[7] is not None for r in drafts),
        "mapped_counterparts": Counter(r[6] for r in drafts if r[6] is not None),
        "unresolved_counterpart_rows": unresolved,
        "march_opening_minus_february_closing": opening_differences,
        "march_workbook_minus_calculated_closing": closing_differences,
        "bank_control": control,
    }, indent=2, default=str))
    if args.apply and blocked:
        parser.error("March has unresolved source controls. No journals were written.")
    if not args.source_only:
        run_db(args, drafts, control, source, start=START, end=END, tab=TAB, prefix=PREFIX,
               fees={}, splits=SPLIT, location_overrides=LOCATIONS, supporting_details={2052: 286})


if __name__ == "__main__":
    main()
