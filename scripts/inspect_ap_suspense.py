"""Inspect AP Suspense / GRNI imbalance from posted journals.

Read-only. Prints totals, per-supplier balances, and contributing journals.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.core.database import SessionLocal

ACCOUNT_NO = "200-100-999"
ZERO = Decimal("0.00")


def money(value):
    return f"{Decimal(value or 0):,.2f}"


def main():
    db = SessionLocal()
    try:
        coa = db.execute(text("""
            SELECT id, account_number, account_name, normal_balance
            FROM chart_of_accounts
            WHERE account_number = :account_no
        """), {"account_no": ACCOUNT_NO}).mappings().first()
        if not coa:
            raise RuntimeError(f"COA {ACCOUNT_NO} not found")

        print(f"AP Suspense: {coa['account_number']} - {coa['account_name']} ({coa['normal_balance']})")

        totals = db.execute(text("""
            SELECT
                COALESCE(SUM(jl.debit),0) AS debit,
                COALESCE(SUM(jl.credit),0) AS credit
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.journal_entry_id
            WHERE jl.account_id = :account_id
              AND je.status = 'POSTED'
        """), {"account_id": coa["id"]}).mappings().one()

        debit = Decimal(totals["debit"])
        credit = Decimal(totals["credit"])
        credit_normal_balance = credit - debit
        print("\n=== CONTROL TOTAL ===")
        print("Debit :", money(debit))
        print("Credit:", money(credit))
        print("Credit-normal balance:", money(credit_normal_balance))

        by_type = db.execute(text("""
            SELECT
                je.reference_type,
                COUNT(DISTINCT je.id) AS journals,
                COALESCE(SUM(jl.debit),0) AS debit,
                COALESCE(SUM(jl.credit),0) AS credit
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.journal_entry_id
            WHERE jl.account_id = :account_id
              AND je.status = 'POSTED'
            GROUP BY je.reference_type
            ORDER BY je.reference_type
        """), {"account_id": coa["id"]}).mappings().all()

        print("\n=== BY REFERENCE TYPE ===")
        for r in by_type:
            bal = Decimal(r["credit"]) - Decimal(r["debit"])
            print(f"{r['reference_type']:<24} journals={r['journals']:<4} Dr={money(r['debit']):>16} Cr={money(r['credit']):>16} Bal={money(bal):>16}")

        supplier_rows = db.execute(text("""
            SELECT
                COALESCE(s.name, '(no supplier)') AS supplier,
                jl.supplier_id,
                COALESCE(SUM(jl.debit),0) AS debit,
                COALESCE(SUM(jl.credit),0) AS credit
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.journal_entry_id
            LEFT JOIN suppliers s ON s.id = jl.supplier_id
            WHERE jl.account_id = :account_id
              AND je.status = 'POSTED'
            GROUP BY jl.supplier_id, s.name
            HAVING COALESCE(SUM(jl.credit),0) <> COALESCE(SUM(jl.debit),0)
            ORDER BY ABS(COALESCE(SUM(jl.credit),0)-COALESCE(SUM(jl.debit),0)) DESC
        """), {"account_id": coa["id"]}).mappings().all()

        print("\n=== NON-ZERO BY SUPPLIER ===")
        for r in supplier_rows:
            bal = Decimal(r["credit"]) - Decimal(r["debit"])
            print(f"{r['supplier']:<35} Dr={money(r['debit']):>16} Cr={money(r['credit']):>16} Bal={money(bal):>16}")

        journals = db.execute(text("""
            SELECT
                je.id,
                je.posting_date,
                je.journal_number,
                je.reference_type,
                je.reference_id,
                je.document_number,
                COALESCE(s.name, '(no supplier)') AS supplier,
                jl.supplier_id,
                jl.debit,
                jl.credit,
                jl.description
            FROM journal_lines jl
            JOIN journal_entries je ON je.id = jl.journal_entry_id
            LEFT JOIN suppliers s ON s.id = jl.supplier_id
            WHERE jl.account_id = :account_id
              AND je.status = 'POSTED'
            ORDER BY je.posting_date, je.id, jl.id
        """), {"account_id": coa["id"]}).mappings().all()

        print("\n=== CONTRIBUTING POSTED JOURNALS ===")
        for r in journals:
            signed = Decimal(r["credit"]) - Decimal(r["debit"])
            print(
                f"{r['posting_date']}  {r['journal_number']:<18} "
                f"{r['reference_type']:<18} ref={str(r['reference_id']):<6} "
                f"{r['supplier']:<28} Dr={money(r['debit']):>14} Cr={money(r['credit']):>14} "
                f"Bal={money(signed):>14}  {r['document_number'] or ''}"
            )

        # Reconstruct receipt-side and invoice-side clearing by supplier.
        gr = defaultdict(Decimal)
        si = defaultdict(Decimal)
        names = {}
        for r in journals:
            sid = r["supplier_id"]
            names[sid] = r["supplier"]
            if r["reference_type"] == "GOODS_RECEIPT":
                gr[sid] += Decimal(r["credit"]) - Decimal(r["debit"])
            elif r["reference_type"] == "SUPPLIER_INVOICE":
                # Supplier invoices should debit AP Suspense, so convert to positive clearing.
                si[sid] += Decimal(r["debit"]) - Decimal(r["credit"])

        print("\n=== GR CREDIT VS SI CLEARING BY SUPPLIER ===")
        for sid in sorted(set(gr) | set(si), key=lambda x: abs(gr[x]-si[x]), reverse=True):
            diff = gr[sid] - si[sid]
            if diff == ZERO:
                continue
            print(
                f"{names.get(sid,'(no supplier)'):<35} "
                f"GR credit={money(gr[sid]):>16} "
                f"SI clearing={money(si[sid]):>16} "
                f"remaining={money(diff):>16}"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()
