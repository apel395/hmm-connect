"""Read-only Hotel January journal source preparation; deliberately no apply mode."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE_SHA256 = "045a54343005ee0c3cbd130838dd292c594ae434452abbf9b19578f99bc22507"
SHEET = "gljournalTransactionbyregist.rp"
ZERO = Decimal("0.00")
# Suggestions only: finance must confirm each mapping in the review file.
DEPARTMENT_SUGGESTIONS = {
    "FO": "Front Office", "HK": "House Keeping", "FBS": "Food and Beverage",
    "FBP": "Food and Beverage", "PMC": "Pomec", "A&G": "Admin and General",
    "H&R": "Human Resources", "S&M": "Sales and Marketing",
}


def money(value):
    if value in (None, ""):
        return ZERO
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid source amount: {value!r}") from exc
    if not result.is_finite() or result != result.quantize(Decimal("0.01")):
        raise ValueError(f"Non-cent source amount: {value!r}")
    return result.quantize(Decimal("0.01"))


def identifier(value):
    if isinstance(value, (float, int)) and value == int(value):
        return str(int(value))
    return str(value).strip()


def mapping_code(value):
    text = str(value).strip()
    return text if re.fullmatch(r"\d+(?:-\d+)+", text) else None


def read_source(path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError("Source hash changed. Inspect the new workbook before preparing it.")
    import xlrd  # EC2 worker dependency only; never added to Lambda requirements.
    book = xlrd.open_workbook(str(path))
    sheet = book.sheet_by_name(SHEET)
    expected = {0: "No.", 1: "Date", 2: "Register", 3: "Code", 8: "DC", 11: "Debet", 12: "Credit"}
    if any(sheet.cell_value(9, col) != label for col, label in expected.items()):
        raise ValueError("Unexpected workbook column layout")
    groups = {}
    controls = []
    sequences = []
    current = None
    for index in range(10, sheet.nrows):
        cells = sheet.row(index)
        row = [c.value for c in cells]
        source_row = index + 1
        # A real detail row has a numeric sequence and a typed Excel date.
        detail = cells[0].ctype == xlrd.XL_CELL_NUMBER and cells[1].ctype == xlrd.XL_CELL_DATE
        header = not detail and cells[2].ctype == xlrd.XL_CELL_NUMBER and any(
            cells[col].ctype == xlrd.XL_CELL_DATE for col in (0, 1)
        )
        if header:
            register = identifier(row[2])
            if register in groups:
                raise ValueError(f"Repeated header register {register} at row {source_row}")
            col = 0 if cells[0].ctype == xlrd.XL_CELL_DATE else 1
            current = {
                "register": register, "external_reference": f"HOTEL-JAN2026-REG-{register}",
                "header_row": source_row,
                "posting_date": xlrd.xldate_as_datetime(row[col], book.datemode).date().isoformat(),
                "description": str(row[3]).strip(), "invoice_reference": str(row[9]).strip(),
                "lines": [],
            }
            groups[register] = current
        elif detail:
            if current is None or identifier(row[2]) != current["register"]:
                raise ValueError(f"Detail without matching register header at row {source_row}")
            if any(c.ctype == xlrd.XL_CELL_ERROR for c in cells):
                raise ValueError(f"Formula error on financial detail row {source_row}")
            sequence = int(row[0])
            sequences.append(sequence)
            name = str(row[4]).strip()
            prefix = name.split(" - ")[0].strip() if " - " in name else None
            debit, credit = money(row[11]), money(row[12])
            current["lines"].append({
                "source_row": source_row, "sequence": sequence,
                "posting_date": xlrd.xldate_as_datetime(row[1], book.datemode).date().isoformat(),
                "legacy_code": identifier(row[3]), "legacy_name": name,
                "source_account_code": mapping_code(row[5]),
                "account_code": mapping_code(row[5]),
                "department_prefix": prefix,
                "suggested_department": DEPARTMENT_SUGGESTIONS.get(prefix),
                "description": str(row[6]).strip(), "invoice_reference": str(row[9]).strip(),
                "source_dc": str(row[8]).strip().upper(),
                "debit": str(debit), "credit": str(credit),
            })
        elif re.sub(r"\s", "", str(row[8])).upper() == "TOTAL":
            controls.append({"source_row": source_row, "debit": str(money(row[11])), "credit": str(money(row[12]))})
        elif (row[11] not in ("", 0) or row[12] not in ("", 0)) and not (
            str(row[8]).strip() == "SUB TOTAL" or all(row[col] == "" for col in (0, 1, 2, 3, 6, 8, 9))
        ):
            raise ValueError(f"Unrecognized monetary row {source_row}; inspection required")
    if len(controls) != 1:
        raise ValueError("Expected exactly one grand-total control")
    if len(sequences) != len(set(sequences)):
        raise ValueError("Duplicate detail sequence")
    missing = sorted(set(range(1, max(sequences) + 1)) - set(sequences))
    return {"source_sha256": digest, "source_file": path.name, "sheet": SHEET,
            "journals": list(groups.values()), "grand_total": controls[0], "missing_sequences": missing}


def inspect_database():
    """All database SQL runs in a PostgreSQL READ ONLY transaction."""
    from sqlalchemy import text
    from app.core.database import engine

    queries = {
        "accounts": "SELECT id,account_number,account_name,account_type,is_posting,is_active FROM chart_of_accounts",
        "units": "SELECT id,name,is_active FROM business_units",
        "locations": "SELECT id,name,business_unit_id,is_active FROM locations",
        "departments": "SELECT id,name,business_unit_id,is_active FROM departments",
        "location_departments": "SELECT location_id,department_id FROM location_departments",
        "periods": "SELECT fiscal_year,fiscal_month,start_date,end_date,is_open,is_closed,allow_backdated_entries FROM fiscal_periods WHERE fiscal_year=2026 AND fiscal_month=1",
        # Include void/draft records; reimporting must be an explicit decision.
        "journals": "SELECT id,journal_number,document_number,external_reference,status,posting_date,business_unit_id,location_id FROM journal_entries WHERE posting_date BETWEEN '2026-01-01' AND '2026-01-31' OR external_reference LIKE 'HOTEL-JAN2026-REG-%'",
    }
    with engine.connect() as connection:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            return {key: [dict(row) for row in connection.execute(text(sql)).mappings()] for key, sql in queries.items()}


def build_plan(source, database=None, review=None):
    review = review or {}
    accounts = {a["account_number"]: a for a in (database or {}).get("accounts", [])}
    scope = review.get("scope", {})
    scope_issues = []
    if database is None:
        scope_issues.append("DATABASE_NOT_CHECKED")
    else:
        units = [u for u in database["units"] if u["is_active"] and u["id"] == scope.get("business_unit_id") and "hotel" in u["name"].lower()]
        locations = [l for l in database["locations"] if l["is_active"] and l["id"] == scope.get("location_id") and l["business_unit_id"] == scope.get("business_unit_id")]
        if len(units) != 1 or len(locations) != 1:
            scope_issues.append("HOTEL_SCOPE_CONFIRMATION_REQUIRED")
        periods = database["periods"]
        if len(periods) != 1 or not periods[0]["is_open"] or periods[0]["is_closed"] or not periods[0]["allow_backdated_entries"] or str(periods[0]["start_date"]) > "2026-01-01" or str(periods[0]["end_date"]) < "2026-01-31":
            scope_issues.append("JANUARY_PERIOD_NOT_OPEN_FOR_HISTORICAL_ENTRY")
    if review and review.get("source_sha256") != source["source_sha256"]:
        raise ValueError("Review mapping source hash mismatch")
    counts = Counter()
    account_review = {}
    dept_review = {}
    total_debit = total_credit = ZERO
    dc_mismatches = zero_lines = unmapped_lines = 0
    unbalanced = []
    for journal in source["journals"]:
        issues = set(scope_issues)
        debit = credit = ZERO
        if not "2026-01-01" <= journal["posting_date"] <= "2026-01-31":
            issues.add("OUTSIDE_JANUARY_2026")
        for line in journal["lines"]:
            line_issues = []
            d, c = money(line["debit"]), money(line["credit"])
            debit += d
            credit += c
            if d == c == 0:
                zero_lines += 1
                line["omit_zero_value"] = True
                continue
            if d < 0 or c < 0 or (d and c):
                line_issues.append("INVALID_AMOUNT_SIDES")
            if line["posting_date"] != journal["posting_date"]:
                line_issues.append("HEADER_DETAIL_DATE_CONFLICT")
            if line["source_dc"] != ("D" if d else "C"):
                dc_mismatches += 1
            legacy = line["legacy_code"]
            line["account_code"] = review.get("accounts", {}).get(legacy) or line["source_account_code"]
            code = line["account_code"]
            if not code:
                line_issues.append("COA_MAPPING_REQUIRED")
                unmapped_lines += 1
            elif database is not None:
                account = accounts.get(code)
                if not account or not account["is_active"] or not account["is_posting"] or account["account_type"] == "STATISTIC":
                    line_issues.append("COA_NOT_ACTIVE_FINANCIAL_POSTING_ACCOUNT")
                else:
                    line["account_id"] = account["id"]
            prefix = line["department_prefix"]
            dept_id = review.get("departments", {}).get(prefix) if prefix else None
            # Department evidence is required for P&L; never infer from an invoice reference.
            pnl = (code or "").startswith(("4", "5", "6", "7", "8")) or prefix in DEPARTMENT_SUGGESTIONS or prefix in {"BOD", "SWP", "LDY"}
            if pnl and dept_id is None:
                line_issues.append("DEPARTMENT_CONFIRMATION_REQUIRED")
            if dept_id is not None and database is not None:
                eligible = [dep for dep in database["departments"] if dep["id"] == dept_id and dep["is_active"] and dep["business_unit_id"] == scope.get("business_unit_id")]
                linked = any(link["department_id"] == dept_id and link["location_id"] == scope.get("location_id") for link in database["location_departments"])
                if len(eligible) != 1 or not linked:
                    line_issues.append("DEPARTMENT_NOT_IN_HOTEL_LOCATION")
                else:
                    line["department_id"] = dept_id
            line["issues"] = line_issues
            issues.update(line_issues)
            key = legacy
            entry = account_review.setdefault(key, {"legacy_code": legacy, "legacy_name": line["legacy_name"], "source_codes": set(), "lines": 0, "debit": ZERO, "credit": ZERO})
            if line["source_account_code"]:
                entry["source_codes"].add(line["source_account_code"])
            entry["lines"] += 1
            entry["debit"] += d
            entry["credit"] += c
            if pnl:
                dep = dept_review.setdefault(prefix or "UNRESOLVED", {"prefix": prefix, "suggested_department": line["suggested_department"], "lines": 0, "example": line["legacy_name"]})
                dep["lines"] += 1
        total_debit += debit
        total_credit += credit
        difference = debit - credit
        if difference:
            issues.add("UNBALANCED_SOURCE_REGISTER")
            unbalanced.append({"register": journal["register"], "header_row": journal["header_row"], "difference": str(difference)})
        if not debit and not credit:
            issues.add("NO_FINANCIAL_LINES")
        if database is not None:
            matches = []
            for existing in database["journals"]:
                stable = existing["external_reference"] == journal["external_reference"]
                # Exact legacy register matching, not repeated invoice/reference descriptions.
                legacy_match = journal["register"] in {existing["journal_number"], existing["document_number"], existing["external_reference"]}
                if stable or legacy_match:
                    matches.append(existing)
            if matches:
                issues.add("EXISTING_REGISTER_REVIEW")
                journal["existing_journals"] = matches
        journal.update(debit=str(debit), credit=str(credit), difference=str(difference), issues=sorted(issues), status="REVIEW" if issues else "READY_FOR_SEED_REVIEW")
        counts[journal["status"]] += 1
    control_matches = total_debit == money(source["grand_total"]["debit"]) and total_credit == money(source["grand_total"]["credit"])
    if not control_matches:
        raise ValueError("Detail sums do not match the workbook grand totals")
    for entry in account_review.values():
        entry["source_codes"] = sorted(entry["source_codes"])
        entry["debit"], entry["credit"] = str(entry["debit"]), str(entry["credit"])
        if len(entry["source_codes"]) > 1:
            raise ValueError(f"Inconsistent source COA for legacy code {entry['legacy_code']}")
    issue_counts = Counter(issue for journal in source["journals"] for issue in journal["issues"])
    summary = {"mode": "READ_ONLY_PREPARATION", "source_sha256": source["source_sha256"], "source_file": source["source_file"],
               "journals": len(source["journals"]), "detail_lines": sum(len(j["lines"]) for j in source["journals"]),
               "zero_lines_omitted_from_future_posting": zero_lines, "debit": str(total_debit), "credit": str(total_credit),
               "difference": str(total_debit - total_credit), "grand_totals_match": control_matches,
               "dc_label_conflicts_using_amount_columns": dc_mismatches, "unmapped_nonzero_lines": unmapped_lines,
               "unbalanced_registers": unbalanced, "missing_sequences": source["missing_sequences"],
               "database_checked": database is not None, "statuses": dict(counts), "review_counts": dict(issue_counts),
               "seed_ready": False, "reason": "Preparation only. No apply mode; resolve mappings, scope, departments and source differences before generating a seed batch."}
    return {"summary": summary, "source": source, "account_review": list(account_review.values()), "department_review": list(dept_review.values()), "database": database}


def write_outputs(plan, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".json").write_text(json.dumps(plan, indent=2, default=str) + "\n")
    fields = ["register", "header_row", "posting_date", "source_row", "legacy_code", "legacy_name", "account_code", "department_prefix", "suggested_department", "debit", "credit", "description", "issues"]
    with output.with_suffix(".csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for journal in plan["source"]["journals"]:
            for line in journal["lines"]:
                record = {field: line.get(field, journal.get(field, "")) for field in fields}
                record["issues"] = "; ".join(sorted(set(journal["issues"]) | set(line.get("issues", []))))
                # Preserve text literally when opening the CSV in Excel.
                writer.writerow({key: "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) else value for key, value in record.items()})
    template = {"source_sha256": plan["summary"]["source_sha256"], "scope": {"business_unit_id": None, "location_id": None},
                "accounts": {row["legacy_code"]: row["source_codes"][0] if row["source_codes"] else None for row in plan["account_review"]},
                "departments": {row["prefix"]: None for row in plan["department_review"] if row["prefix"]}}
    # A rerun must never overwrite finance's completed review mapping.
    template_path = output.with_name(output.name + "-mapping-template").with_suffix(".json")
    if not template_path.exists():
        template_path.write_text(json.dumps(template, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--db-check", action="store_true")
    parser.add_argument("--mapping-file", type=Path)
    parser.add_argument("--output", type=Path, default=Path("/tmp/hotel-january-journal-plan"))
    args = parser.parse_args()
    review = json.loads(args.mapping_file.read_text()) if args.mapping_file else None
    plan = build_plan(read_source(args.source), inspect_database() if args.db_check else None, review)
    write_outputs(plan, args.output)
    print(json.dumps(plan["summary"], indent=2))
    print(f"Full plan: {args.output.with_suffix('.json')}")
    print(f"Line review: {args.output.with_suffix('.csv')}")
    print("READ ONLY: no journals, GL, openings, source documents, stock or master data changed.")


if __name__ == "__main__":
    main()
