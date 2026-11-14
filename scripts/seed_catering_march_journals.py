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
LOCATIONS = {
    56: "Pekanbaru",  # Shared training for DOBS, PHM, and PRCC without allocation amounts.
    **dict.fromkeys((211, 347, 349, 350, 1330, 1334), "Gemsmart Duri"),
}
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

    # Row 2009 is the funding header. Its breakdown contains spending and
    # returned cash, whose actual bank dates fall in April.
    csr_header = source[2008]
    csr_detail = source[2009:2018]
    csr_amount = Decimal("5155000.00")
    if (csr_header[0] != datetime(2026, 3, 31) or account(csr_header[3]) != 116
            or "CSR PROJECT" not in csr_header[3] or money(csr_header[4]) or money(csr_header[5])
            or any(row[0] != csr_header[0] or account(row[2]) != 117 for row in csr_detail)
            or sum(money(row[5]) - money(row[4]) for row in csr_detail) != csr_amount):
        raise ValueError("March CSR funding breakdown changed")
    details.update(range(2010, 2019))

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

    csr = movements[2052]
    if csr[3:6] != (117, Decimal("5155000"), 0) or "CSR PROJECT" not in csr[2]:
        raise ValueError("CSR receipt evidence changed")
    paired[2052] = (2009, 116)
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


def verify_february_correction():
    from sqlalchemy import text

    from app import models  # noqa: F401
    from app.core.database import SessionLocal
    from app.models.business_unit import BusinessUnit
    from app.models.journal_entry import JournalEntry

    with SessionLocal() as db, db.begin():
        db.execute(text("SET TRANSACTION READ ONLY"))
        unit = db.query(BusinessUnit).filter_by(name="Project Catering", is_active=True).one()
        entries = db.query(JournalEntry).filter_by(
            external_reference="KH-CATERING-2026-02-EKI-TAX-2124",
            business_unit_id=unit.id,
            posting_date=date(2026, 2, 28),
        ).all()
        if len(entries) != 1:
            return False
        entry = entries[0]
        return entry.status in {"DRAFT", "POSTED"} and sorted(
            (line.account.account_number, line.debit, line.credit) for line in entry.lines
        ) == [("100-110-117", 0, Decimal("165.04")), ("760-100-102", Decimal("165.04"), 0)]


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
    eki = "100-110-117"
    raw_prior_eki = prior_closing[eki]
    if raw_prior_eki == Decimal("3347846.17") and control[eki]["opening"] == Decimal("3347681.13"):
        if args.source_only or verify_february_correction():
            prior_closing[eki] -= Decimal("165.04")
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
        "ready_to_apply": not blocked and not args.source_only,
        "february_eki_correction_verified_in_db": not args.source_only and prior_closing[eki] != raw_prior_eki,
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
               fees={}, splits=SPLIT, location_overrides=LOCATIONS, supporting_details={2052: 2009})


if __name__ == "__main__":
    main()
