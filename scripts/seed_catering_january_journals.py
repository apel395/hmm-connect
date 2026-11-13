"""Seed Project Catering January 2026 Kas Harian into editable manual drafts."""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from urllib.request import urlopen

from openpyxl import load_workbook

URL = "https://docs.google.com/spreadsheets/d/1Ey0aHSLZaFQ4smFt8v2ae_y7wEzVuC7L/export?format=xlsx"
TAB = "DONE KAS HARIAN JAN"
PREFIX = "KH-CATERING-2026-01-"
TRANSPORT_COA = "700-500-100"
EXPENSE_RULES = {
    "700-500-122": r"\b(?:ADMIN(?:ISTRASI)?\s+BANK|BIAYA\s+ADMIN\s+TRANSFER|BIAYA\s+ADM)\b",
    TRANSPORT_COA: r"\b(?:PARKIR|TOP\s*UP\s+TOL|BAYAR\s+TOL|BAYAR\s+TRANSPORT)\b",
    "700-500-125": r"\b(?:KIRIM\s+DOKUMEN|BIAYA\s+KURIR)\b",
}
LOCATION_OVERRIDES = {
    148: "Gemsmart Duri", 339: "Pekanbaru", "0376-PHM": "PHM", "0376-DOBS": "DOBS",
    852: "DOBS", 859: "PRCC", 860: "PRCC", 903: "PHM", 905: "PRCC",
    924: "PRCC", 936: "PRCC", 1479: "PRCC", 1511: "PRCC",
}
SPLIT_376 = {"0376-PHM": Decimal("8935000"), "0376-DOBS": Decimal("6216000")}
ACCOUNTS = {
    100: "1080012525250", 101: "1080053252525 10800053252525",
    102: "1080025915225", 103: "193684771 0193684771",
    104: "7003724667", 105: "1003488221", 106: "107901000207301",
    107: "1490800353", 116: "1080070025250 10800070025250",
    117: "1080525000205", 118: "1080525000304", 119: "1080525000106",
    120: "650 0065201300000650 06520130000650", 121: "1080080252522",
    122: "1080072252522", 123: "1080079252525",
}
BANK = {103: "BNI", 104: "BSI", 105: "BUKOPIN", 106: "BRI", 107: "BRK", 120: "BTN"}
OVERRIDES = {940: 119, 1455: 118, 2110: 118}
TRANSFERS = {
    388: (255, 116, 117, 20000000), 814: (480, 102, 118, 79505000),
    958: (850, 116, 119, 50000000), 1552: (1163, 102, 118, 80000000),
    1561: (1473, 116, 119, 50000000), 1779: (1698, 116, 119, 50000000),
    2137: (1831, 102, 118, 80000000),
}
PATTERNS = [
    (re.compile(r"^\s*" + BANK.get(key, "MANDIRI") + r"[ .,:-]*" +
                r"[ .,-]*".join(number) + r"(?!\d)", re.I), key)
    for key, values in ACCOUNTS.items() for number in values.split()
]


def account(value):
    value = str(value or "").strip()
    for pattern, key in PATTERNS:
        if pattern.match(value):
            return key
    label = re.match(r"^(BRK|BSI|BRI|BUKOPIN)\b", value, re.I)
    return next((key for key, name in BANK.items() if label and label[1].upper() == name), None)


def money(value):
    if value is None or value == "":
        return Decimal(0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Unexpected monetary cell: {value!r}")
    return Decimal(str(value)).quantize(Decimal(".01"))


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def load_source(path):
    if path:
        data = path.read_bytes()
    else:
        with urlopen(URL, timeout=60) as response:
            data = response.read()
    if not data.startswith(b"PK"):
        raise ValueError("Spreadsheet export did not return XLSX. Supply an authorized export with --xlsx.")
    with BytesIO(data) as stream:
        workbook = load_workbook(stream, read_only=True, data_only=True)
        try:
            return list(workbook[TAB].iter_rows(max_col=7, values_only=True))
        finally:
            workbook.close()


def journal_reference(row):
    return PREFIX + (f"{row:04d}" if isinstance(row, int) else row)


def expense_counterpart(memo):
    matches = [code for code, pattern in EXPENSE_RULES.items() if re.search(pattern, memo, re.I)]
    return matches[0] if len(matches) == 1 else None


def prepare(rows):
    if rows[4][3:7] != ("KETERANGAN", "DEBET", "KREDIT", "SALDO"):
        raise ValueError("Unexpected January header")
    if not str(rows[21][3]).startswith("TOTAL SALDO") or str(rows[2292][3]).strip() != "MUTASI":
        raise ValueError("January transaction range changed")
    opening = {account(r[3].split("(")[-1].split(")")[0]): money(r[4]) for r in rows[5:21]}
    closing = {account(r[4]): money(r[6]) for r in rows[2305:2321]}
    if set(opening) != set(closing) or set(closing) != set(ACCOUNTS):
        raise ValueError("January account controls changed")
    source_totals = [Decimal(0), Decimal(0)]
    movements = Counter()
    drafts = []
    transfer_rows = set()
    for number, row in enumerate(rows[22:2292], 23):
        stamp, _, receipt, memo, debit, credit, _ = row
        debit, credit = money(debit), money(credit)
        if not (debit or credit):
            continue
        if (debit > 0) == (credit > 0) or min(debit, credit) < 0:
            raise ValueError(f"Unexpected debit/credit on row {number}")
        if not isinstance(stamp, datetime) or (stamp.year, stamp.month) != (2026, 1):
            raise ValueError(f"Invalid date on row {number}")
        source_totals[0] += debit
        source_totals[1] += credit
        choices = {key for key in (account(receipt), account(memo)) if key is not None}
        if number in OVERRIDES and not choices:
            choices = {OVERRIDES[number]}
        if len(choices) != 1:
            raise ValueError(f"Unresolved or conflicting bank on row {number}")
        key = choices.pop()
        bank = f"100-110-{key}"
        contra = expense_counterpart(str(memo or "")) if credit else None
        sender_row = None
        if number in TRANSFERS:
            sender_row, sender, recipient, expected = TRANSFERS[number]
            hint = rows[sender_row - 1]
            if (stamp, key, debit, credit) != (hint[0], recipient, expected, 0) or (
                account(hint[3]) != sender or money(hint[4]) or money(hint[5])
                or "PENAMBAHAN PETTY CASH" not in str(hint[3]).upper()
            ):
                raise ValueError(f"Transfer evidence changed for rows {sender_row}/{number}")
            contra = f"100-110-{sender}"
            movements[sender] -= debit
            transfer_rows.add(number)
        movements[key] += debit - credit
        drafts.append((number, stamp.date(), str(memo or ""), bank, debit, credit, contra, sender_row))
    expected_totals = [Decimal("55173574078.38"), Decimal("52723837252.28")]
    if len(drafts) != 2262 or transfer_rows != set(TRANSFERS) or source_totals != expected_totals:
        raise ValueError("January source totals or row count changed")
    if sum(opening.values()) + source_totals[0] - source_totals[1] != sum(closing.values()):
        raise ValueError("Workbook aggregate balance does not reconcile")
    control = {f"100-110-{key}": {
        "opening": opening[key], "net_seed": movements[key],
        "workbook_closing": closing[key],
        "workbook_minus_seed_closing": closing[key] - opening[key] - movements[key],
    } for key in sorted(opening)}
    journals = []
    for row, stamp, memo, bank, debit, credit, contra, sender in drafts:
        if row == 376:
            if debit or credit != sum(SPLIT_376.values()) or sender is not None:
                raise ValueError("Row 376 no longer matches the approved PHM/DOBS split")
            journals.extend((ref, stamp, memo, bank, debit, amount, contra, sender)
                            for ref, amount in SPLIT_376.items())
        else:
            journals.append((row, stamp, memo, bank, debit, credit,
                             TRANSPORT_COA if row == 339 else contra, sender))
    return journals, control


VERIFIED_TRANSFER_PAIRS = (
    (35, 39), (37, 38), (224, 252), (405, 407), (473, 796), (844, 941),
    (847, 849), (1018, 996), (1105, 1081), (1112, 1127), (1150, 1136),
    (1158, 1470), (1159, 1544), (1162, 1472), (1563, 1593), (1566, 1582),
    (1828, 2120), (394, 253), (816, 795),
)


# Reviewed January transfer pairs, including the sender's bank charge where applicable.
ADDITIONAL_PAIRS = (
    (1557, 1461), (2140, 2116), (1794, 2150), (1793, 1806), (1796, 1807),
    (2153, 2177), (2155, 2176), (2156, 2175),
    (1674, 1691), (1676, 1692), (1677, 1693), (1678, 1694), (1679, 1695), (1681, 1696),
)
TRANSFER_FEES = {2177: Decimal("2900"), 2176: Decimal("2500"), 2175: Decimal("2500")}
COUNTERPART_OVERRIDES = {
    "100-210-999": {49, 395, 1079, 1080, 1128, 1778, 1817, 1820},
    "200-300-999": {401, 429, 1130, 2151, 990, 991, 993, 994, 995, 1013},
    "700-500-127": {1687, 1760},
    "200-200-100": {1675},
    "200-100-1": {1609, 2154},
    "100-200-101": {174, 179, 181, 195, 417, 418, 832, 1602, 1774, 2180},
    "200-300-106": {62},
    "200-700-105": {402},
    "200-400-104": {1009},
    "760-100-102": {1667, 2219, 2256, 2259, 2262, 2268, 2274, 2280, 2283, 2286, 2289, 2291},
}
SUPPORTING_DETAILS = {389: 256, 390: 257, 391: 258, 392: 260, 393: 261}
SALES_RECEIPT = (
    r"SETOR(?:AN)?\s+(?:HASIL\s+)?PENJUALAN|SALES\s+PENJUALAN|TERIMA\s+PENJUALAN"
    r"|MESIN\s+EDC|SETTLEMENT\s+EDC|(?:TERIMA|PENERIMAAN|PELUNASAN|BAYAR)\s+"
    r"(?:TAG(?:IHAN)?\s*\.?\s*INV|INVOICE|TAGIHAN)"
)


def resolve_counterpart(row, source):
    number, _, memo, _, debit, credit, counterpart, _ = row
    if counterpart:
        return counterpart, "Existing seed mapping"
    for code, references in COUNTERPART_OVERRIDES.items():
        if number in references:
            return code, "January source-row mapping for review"
    if number in SUPPORTING_DETAILS:
        memo = source[SUPPORTING_DETAILS[number] - 1][3]
    memo = memo.upper()
    if debit:
        if re.search(SALES_RECEIPT, memo):
            return "100-200-101", "Sales and invoice receipts"
        if re.search(r"TERIMA\s+KMK", memo):
            return "200-300-104", "KMK M-71 drawdown"
        if re.search(r"BUNGA|JASA GIRO", memo):
            return "760-100-100", "Bank interest received"
        raise ValueError(f"Unmapped January receipt on row {number}")
    rules = (
        (r"FASILITAS\s+BUNGA.*KMK", "760-100-103"),
        (r"PELUNASAN\s+KMK|ANGSURAN\s+BAKI\s+DEBIT\s+KMK", "200-300-104"),
        (r"CASH ADVANCE", "100-210-999"), (r"BPJS KES", "200-200-112"),
        (r"BPJS TK", "200-200-113"), (r"PAYROLL", "200-200-100"),
        (r"CASUAL", "200-200-120"), (r"POTONGAN PPH21", "200-400-102"),
        (r"\bPB1\b", "200-400-100"), (r"\bPPH FINAL\b", "200-400-105"),
        (r"\bPPH23\b", "200-400-103"),
    )
    for pattern, code in rules:
        if re.search(pattern, memo):
            return code, "Transaction description"
    if re.search(r"\b(?:INV(?:OICE)?|TAGIHAN)\b", memo) or credit >= 1_000_000:
        return "200-100-1", "Invoice payment or amount at least IDR 1 million"
    for pattern, code in (
        (r"ADMIN\s+TRAN[SF]FER", "700-500-122"),
        (r"WI.?FI|INTERNET|PULSA|TELEPON", "700-500-107"),
        (r"LISTRIK|\bPLN\b", "700-500-139"), (r"REFILL GALON", "700-500-115"),
    ):
        if re.search(pattern, memo):
            return code, "Direct expense from source description"
    return "700-500-999", "Temporary expense below IDR 1 million"


def consolidate_transfers(drafts):
    by_row = {row[0]: row for row in drafts}
    replacements = {}
    consumed = set()
    for outgoing, incoming in VERIFIED_TRANSFER_PAIRS + ADDITIONAL_PAIRS:
        sender, receiver = by_row[outgoing], by_row[incoming]
        _, stamp, memo, bank, debit, credit, contra, sender_row = receiver
        if ((stamp - sender[1]).days != (1 if incoming == 2150 else 0) or bank == sender[3] or not debit or credit
                or sender[4] or debit + TRANSFER_FEES.get(incoming, 0) != sender[5] or contra or sender[6]
                or sender_row is not None or sender[7] is not None):
            raise ValueError(f"Source transfer pair changed: {outgoing}/{incoming}")
        replacements[incoming] = (incoming, stamp, memo, bank, debit, credit, sender[3], outgoing)
        consumed.add(outgoing)
    return [replacements.get(row[0], row) for row in drafts if row[0] not in consumed]


PETTY_CASH_DETAIL_BLOCKS = (
    (255, 374), (480, 794), (850, 940), (1163, 1455),
    (1473, 1528), (1698, 1758), (1831, 2110),
)


def prepare_seed(rows):
    drafts, control = prepare(rows)
    detail_rows = {row for start, end in PETTY_CASH_DETAIL_BLOCKS for row in range(start + 1, end + 1)}
    details = [row for row in drafts if row[0] in detail_rows]
    if len(details) != 1209 or sum(row[5] - row[4] for row in details) != Decimal("409505000.00"):
        raise ValueError("Petty cash supporting-detail controls changed")
    corrected = []
    for row in drafts:
        if row[0] in detail_rows:
            continue
        if row[0] == 397:
            if row[3] not in {"100-110-117", "100-110-118"} or (row[4], row[5], row[7]) != (0, Decimal("4000.00"), None):
                raise ValueError("Row 397 no longer matches the approved bank correction")
            row = (*row[:3], "100-110-117", *row[4:])
        corrected.append(row)
    journals = []
    for row in consolidate_transfers(corrected):
        counterpart, _ = resolve_counterpart(row, rows)
        journals.append((*row[:6], counterpart, row[7]))
    movement = Counter()
    for number, _, _, bank, debit, credit, contra, sender in journals:
        movement[bank] += debit - credit
        if sender is not None:
            movement[contra] += credit - debit - TRANSFER_FEES.get(number, 0)
    for code, item in control.items():
        item["net_seed"] = movement[code]
        item["workbook_minus_seed_closing"] = item["workbook_closing"] - item["opening"] - movement[code]
    if any(item["workbook_minus_seed_closing"] for item in control.values()):
        raise ValueError("January seed does not reconcile to all workbook bank closing balances")
    return journals, control


def location_matches(memo, location_names):
    words = re.findall(r"[^\W_]+", memo.casefold())
    matches = []
    for name in location_names:
        label = re.findall(r"[^\W_]+", name.casefold())
        if not label:
            continue
        for start in range(len(words) - len(label) + 1):
            if words[start:start + len(label)] == label:
                matches.append((start, start + len(label), name))
    return sorted({
        name for start, end, name in matches
        if not any(left <= start and end <= right and right - left > end - start
                   for left, right, _ in matches)
    })


def assign_locations(drafts, locations, fallback):
    assignments, exceptions = {}, {}
    for row, _, memo, *_ in drafts:
        override = LOCATION_OVERRIDES.get(row)
        if override:
            if override not in locations:
                raise ValueError(f"Approved location {override} for {row} is inactive or missing")
            assignments[row] = locations[override]
            continue
        matches = location_matches(memo, locations)
        if len(matches) == 1:
            assignments[row] = locations[matches[0]]
        else:
            exceptions[row] = {"description": memo, "matches": matches}
            if not matches:
                assignments[row] = fallback
    return assignments, exceptions


def run_db(args, drafts, control, source):
    from sqlalchemy import text
    from app import models  # noqa: F401
    from app.api.v1.journals import validate
    from app.core.database import SessionLocal
    from app.models.business_unit import BusinessUnit
    from app.models.chart_of_account import ChartOfAccount
    from app.models.journal_entry import JournalEntry
    from app.models.journal_line import JournalLine
    from app.models.location import Location
    from app.services.activity_service import ActivityService
    from app.services.document_number import next_document_number
    from app.services.fiscal_period_service import FiscalPeriodService
    from app.services.journal_recognition import FINANCIAL_TYPES, period_state
    from app.services.organization_dimensions import validate_dimensions

    start, end = date(2026, 1, 1), date(2026, 1, 31)
    with SessionLocal() as db, db.begin():
        if args.apply:
            db.execute(text("SET LOCAL lock_timeout = '15s'"))
            FiscalPeriodService.validate_posting_date(db, start)
            db.execute(text("LOCK TABLE journal_entries, journal_lines IN SHARE ROW EXCLUSIVE MODE"))
        else:
            db.execute(text("SET TRANSACTION READ ONLY"))
        target = tuple(db.execute(text(
            "SELECT current_database(), current_schema(), CAST(inet_server_addr() AS text), inet_server_port()"
        )).one())
        unit = db.query(BusinessUnit).filter_by(name="Project Catering", is_active=True).one()
        active = db.query(Location).filter_by(business_unit_id=unit.id, is_active=True).all()
        locations = {item.name: item.id for item in active}
        fallback = locations.get("Pekanbaru")
        if fallback is None:
            raise ValueError("Active Pekanbaru location missing from Project Catering")
        assignments, location_exceptions = assign_locations(drafts, locations, fallback)
        for location_id in set(assignments.values()):
            validate_dimensions(db, business_unit_id=unit.id, location_id=location_id, required=True)
        period, opened = period_state(db, start)
        if not opened or period.end_date < end:
            raise ValueError("An open fiscal period covering January 2026 is required")
        codes = set(control) | {"700-500-122"} | {row[6] for row in drafts if row[6] is not None}
        accounts = {a.account_number: a for a in db.query(ChartOfAccount).filter(
            ChartOfAccount.account_number.in_(codes), ChartOfAccount.is_active.is_(True),
            ChartOfAccount.is_posting.is_(True), ChartOfAccount.account_type.in_(FINANCIAL_TYPES),
        )}
        if set(accounts) != codes or any(accounts[c].account_type != "ASSET" or
                                        accounts[c].account_subtype != "BANK" for c in control):
            raise ValueError(f"Invalid bank or counterpart configuration. Missing posting COA: {sorted(codes - set(accounts))}")
        if any(accounts[code].account_type != "EXPENSE" for code in codes & EXPENSE_RULES.keys()):
            raise ValueError("Expense mapping must use active expense posting accounts")
        refs = {journal_reference(row[0]) for row in drafts}
        existing = db.query(JournalEntry.external_reference, JournalEntry.status).filter(
            JournalEntry.external_reference.like(PREFIX + "%")
        ).all()
        if existing:
            if len(existing) != len(refs) or {r[0] for r in existing} != refs:
                raise ValueError("A partial or conflicting January seed exists. Inspect before retrying.")
            print(json.dumps({"already_present": len(existing), "statuses": dict(Counter(r[1] for r in existing))}))
            return
        by_movement = defaultdict(set)
        for stamp, code, debit, credit, number in db.query(
            JournalEntry.posting_date, ChartOfAccount.account_number, JournalLine.debit,
            JournalLine.credit, JournalEntry.journal_number,
        ).select_from(JournalEntry).join(JournalEntry.lines).join(JournalLine.account).filter(
            JournalEntry.posting_date.between(start, end), JournalEntry.business_unit_id == unit.id,
            JournalEntry.status != "VOID", ChartOfAccount.account_number.in_(control),
        ):
            by_movement[(stamp, code, debit, credit)].add(number)
        candidates = {}
        for row, stamp, _, bank, debit, credit, contra, sender in drafts:
            matches = by_movement[(stamp, bank, debit, credit)].copy()
            if sender:
                matches.update(by_movement[(source[sender - 1][0].date(), contra, credit, debit + TRANSFER_FEES.get(row, 0))])
            if row in SPLIT_376:
                matches.update(by_movement[(stamp, bank, debit, sum(SPLIT_376.values()))])
            if matches:
                candidates[str(row)] = sorted(matches)
        token = fingerprint((target, unit.id, {str(k): v for k, v in assignments.items()},
                             drafts, control, candidates))
        location_counts = Counter(assignments.values())
        report = {"database": target[0], "schema": target[1], "business_unit_id": unit.id,
                  "drafts": len(drafts), "fallback_location_id": fallback,
                  "drafts_by_location": {name: location_counts[id_] for name, id_ in sorted(locations.items())
                                         if location_counts[id_]},
                  "unmatched_location_rows": sum(not item["matches"] for item in location_exceptions.values()),
                  "ambiguous_location_rows": sum(bool(item["matches"]) for item in location_exceptions.values()),
                  "location_exceptions_by_source_row": location_exceptions,
                  "transfer_journals": sum(row[7] is not None for row in drafts),
                  "mapped_counterparts": dict(Counter(row[6] for row in drafts if row[6] is not None)),
                  "missing_counterpart_references": [journal_reference(row[0]) for row in drafts if row[6] is None],
                  "bank_control": control, "possible_existing_journals_by_source_row": candidates,
                  "plan": token}
        print(json.dumps(report, indent=2, default=str))
        if not args.apply:
            return
        if len(assignments) != len(drafts):
            raise ValueError("Some rows match multiple locations. See location_exceptions_by_source_row.")
        if args.expected_plan is not None and args.expected_plan != token:
            raise ValueError("Plan changed or token is wrong. Run dry-run again.")
        for row, stamp, memo, bank, debit, credit, contra, sender in drafts:
            ref = journal_reference(row)
            scope = {"business_unit_id": unit.id, "location_id": assignments[row]}
            journal = JournalEntry(
                journal_number=next_document_number(db, "MAN", digits=6), posting_date=stamp,
                fiscal_year=2026, fiscal_period=1, status="DRAFT", document_type="BULK_JOURNAL_IMPORT",
                document_number=ref, external_reference=ref, reference_type="MANUAL",
                reference_id=0, source_type="JOURNAL_IMPORT", description=memo,
                **scope,
            )
            journal.lines = [
                JournalLine(line_number=1, account_id=accounts[bank].id, debit=debit, credit=credit,
                            description=memo, **scope),
            ]
            fee = TRANSFER_FEES.get(row, Decimal(0))
            journal.lines.append(JournalLine(
                line_number=2, account_id=accounts[contra].id, debit=credit, credit=debit + fee,
                description=memo, **scope,
            ))
            if fee:
                journal.lines.append(JournalLine(
                    line_number=3, account_id=accounts["700-500-122"].id, debit=fee, credit=0,
                    description="Biaya admin transfer sesuai selisih mutasi bank", **scope,
                ))
            if sum(line.debit for line in journal.lines) != sum(line.credit for line in journal.lines):
                raise ValueError(f"Unbalanced journal {ref}")
            validate(db, journal.lines)
            db.add(journal)
            db.flush()
            ActivityService.log(
                db=db, user=None, action="JOURNAL_IMPORT_CREATED", entity_type="JOURNAL_ENTRY",
                entity_id=journal.id, summary=f"Seeded {ref} from Catering Kas Harian",
                document_number=ref, document_status="DRAFT",
                details={"actor": "SYSTEM", "sheet": TAB, "source_row": int(str(row).split("-", 1)[0]), "sender_row": sender,
                                             "proposed_bank_override": row in OVERRIDES,
                                             "approved_bank_override": row == 397,
                                             "location_fallback": row in location_exceptions,
                                             "location_override": LOCATION_OVERRIDES.get(row),
                                             "counterpart_coa": contra, "supporting_row": SUPPORTING_DETAILS.get(row),
                                             "mapping_review": sender is None, "plan": token},
            )
    print(f"COMMITTED {len(drafts)} Project Catering journals as DRAFT.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path, help="Use an authorized local XLSX export instead of Google Sheets")
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--expected-plan")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply and args.source_only:
        parser.error("--apply and --source-only cannot be used together")
    source = load_source(args.xlsx)
    drafts, control = prepare_seed(source)
    if args.source_only:
        print(json.dumps({"drafts": len(drafts),
                          "mapped_counterparts": dict(Counter(row[6] for row in drafts if row[6] is not None)),
                          "missing_counterparts": sum(row[6] is None for row in drafts),
                          "bank_control": control}, indent=2, default=str))
    else:
        run_db(args, drafts, control, source)


if __name__ == "__main__":
    main()
