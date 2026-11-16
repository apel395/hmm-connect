"""Audit May 2026 Project Catering journal candidates from Kas Harian."""
import argparse
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from seed_catering_january_journals import (
    ACCOUNTS, URL, account, load_source, money,
)

from seed_catering_march_journals import counterpart
from seed_catering_april_journals import TAB as APRIL_TAB

TAB = "DONE KAS HARIAN MEI"
START, END = date(2026, 5, 1), date(2026, 5, 31)
TOPUPS = {
    611: (124, 437, 102, 118, 80000000),
    624: (460, 588, 116, 119, 50000000),
    1164: (882, 1135, 102, 118, 80000000),
    1846: (1347, 1658, 102, 118, 80000000),
    1842: (1672, 1799, 116, 117, 20000000),
    1930: (1936, 2085, 116, 119, 50000000),
}
PAIRS = (
    (75,101), (76,100), (439,589), (440,591), (441,592), (443,593),
    (459,438), (618,458), (650,672), (667,646), (668,673), (702,736),
    (703,717), (787,768), (816,789), (874,1150), (878,1149),
    (879,1151), (881,1146), (1136,1152), (1173,1145), (1241,1237),
    (1274,1287), (1275,1288), (1276,1289), (1305,1318), (1306,1331),
    (1307,1319), (1659,1808), (1800,1832), (1802,1833), (1804,1834),
    (1806,1835), (1878,1876), (1879,1872), (1934,2087), (2098,2101),
    (2115,2130), (2116,2141), (2118,2169), (2209,2230), (2211,2229),
    (2219,2213), (2220,2214), (2263,2270), (1897,1875),
)


def prepare(source):
    if (source[4][3:7] != ("KETERANGAN", "DEBET", "KREDIT", "SALDO")
            or not str(source[21][3]).startswith("TOTAL SALDO")
            or str(source[2314][3]).strip() != "MUTASI"):
        raise ValueError("May source layout changed")
    opening = {account(r[3].split("(")[-1].split(")")[0]): money(r[4]) for r in source[5:21]}
    closing = {120 if r[4] == "BTN" else account(r[4]): money(r[6]) for r in source[2327:2343]}
    if set(opening) != set(ACCOUNTS) or set(closing) != set(ACCOUNTS):
        raise ValueError("May bank controls changed")

    details = set()
    for receiver, (header, end, sender, recipient, amount) in TOPUPS.items():
        header_row = source[header - 1]
        receipt = source[receiver - 1]
        if (account(header_row[3]) != sender or header_row[0] != receipt[0]
                or money(header_row[4]) or money(header_row[5])
                or account(receipt[3]) != recipient or money(receipt[4]) != amount
                or money(receipt[5])):
            raise ValueError(f"May petty cash block changed: {header}/{receiver}")
        details.update(range(header + 1, end + 1))

    erwin_rows = set(range(1900, 1912))
    erwin_detail = source[1899:1911]
    if (any(row[0] != datetime(2026, 5, 22) or account(row[3]) != 119
            or money(row[4]) or money(row[5]) <= 0 for row in erwin_detail)
            or sum(money(row[5]) for row in erwin_detail) != Decimal("12688219.00")):
        raise ValueError("The approved Erwin/Desi correction no longer matches the source")

    movements = {}
    for number, row in enumerate(source[23:2314], 24):
        stamp, _, receipt, memo, debit, credit, _ = row
        debit, credit = money(debit), money(credit)
        if number in details or not (debit or credit):
            continue
        keys = {key for key in (account(receipt), account(memo)) if key is not None}
        if number == 2169 and not keys and memo == stamp and debit == 700000000:
            keys = {120}
            memo = "BTN650 - terima transfer Mandiri sesuai baris 2118"
        if (len(keys) != 1 or not isinstance(stamp, datetime) or not START <= stamp.date() <= END
                or min(debit, credit) < 0 or bool(debit) == bool(credit)):
            raise ValueError(f"Invalid May movement at row {number}")
        bank = keys.pop()
        if number in erwin_rows:
            bank = 118
            memo = f"{memo} | Koreksi rekening sumber: Erwin (0304)"
        movements[number] = (number, stamp.date(), str(memo or ""), bank, debit, credit)

    paired = {}
    consumed = set()
    for outgoing, incoming in PAIRS:
        a, b = movements[outgoing], movements[incoming]
        if (abs((b[1] - a[1]).days) > 1 or a[3] == b[3] or a[4] or b[5] or a[5] != b[4]):
            raise ValueError(f"May transfer changed: {outgoing}/{incoming}")
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
            code = counterpart(memo, debit, credit) if number != 1137 else None
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
    parser.add_argument("--xlsx", type=Path, help="Use a local XLSX export instead of Google Sheets")
    args = parser.parse_args()

    if args.xlsx is None:
        with TemporaryDirectory(prefix="kas-harian-may-") as temp:
            workbook = Path(temp) / "kas-harian.xlsx"
            with urlopen(URL, timeout=60) as response:
                workbook.write_bytes(response.read())
            source = load_source(workbook, TAB)
            april = load_source(workbook, APRIL_TAB)
    else:
        source = load_source(args.xlsx, TAB)
        april = load_source(args.xlsx, APRIL_TAB)
    drafts, control = prepare(source)
    prior = {
        f"100-110-{120 if row[4] == 'BTN' else account(row[4])}": money(row[6])
        for row in april[2106:2122]
    }
    if set(prior) != set(control):
        raise ValueError("April closing accounts changed")
    opening_differences = {
        code: item["opening"] - prior[code]
        for code, item in control.items() if item["opening"] != prior[code]
    }
    closing_differences = {
        code: item["workbook_minus_seed_closing"]
        for code, item in control.items() if item["workbook_minus_seed_closing"]
    }
    block_differences = {
        header: total - amount
        for _, (header, end, _, _, amount) in TOPUPS.items()
        if (total := sum(money(r[5]) - money(r[4]) for r in source[header:end])) != amount
    }
    ignored_rounding = {}
    if closing_differences.get("100-110-102") == Decimal("0.32"):
        ignored_rounding["100-110-102"] = closing_differences.pop("100-110-102")
    unresolved = [row[0] for row in drafts if row[6] is None]
    blocked = bool(opening_differences or closing_differences or block_differences or unresolved)
    print(json.dumps({
        "source_controls_pass": not blocked,
        "petty_cash_detail_minus_topup": block_differences,
        "unresolved_counterpart_rows": unresolved,
        "drafts": len(drafts),
        "transfer_journals": sum(row[7] is not None for row in drafts),
        "opening_differences": opening_differences,
        "closing_differences": closing_differences,
        "erwin_reclassified_source_rows": list(range(1900, 1912)),
        "ignored_bank_rounding": ignored_rounding,
        "mapped_counterparts": Counter(row[6] for row in drafts if row[6] is not None),
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
