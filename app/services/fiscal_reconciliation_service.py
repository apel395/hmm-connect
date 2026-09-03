from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import asc, or_
from sqlalchemy.orm import Session

from app.models.chart_of_account import ChartOfAccount
from app.models.fiscal_account import FiscalAccount, FiscalAccountMapping
from app.services.financial_statement_service import FinancialStatementService
from app.services.trial_balance_service import ZERO

PPH_31E_RATE = Decimal("0.11")


class FiscalReconciliationService:
    """Compute the Coretax-style fiscal reconciliation (Rekonsiliasi Fiskal).

    Drives the commercial profit-and-loss (via the posted journal trial balance)
    through the commercial->fiscal mapping and each fiscal account's
    `klasifikasi_fiskal` to derive the fiscal taxable income (Laba Fiskal / PKP)
    and estimated corporate income tax (PPh Badan, Pasal 31E 11%).
    """

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _period_amount(row: dict) -> Decimal:
        """Normal-balance adjusted period amount: revenue positive, expense negative."""
        if row["account_type"] == "REVENUE":
            return Decimal(row.get("period_credit") or ZERO) - Decimal(row.get("period_debit") or ZERO)
        return Decimal(row.get("period_debit") or ZERO) - Decimal(row.get("period_credit") or ZERO)

    def report(
        self,
        *,
        date_from: date,
        date_to: date,
        location_id: int | None = None,
        department_id: int | None = None,
        business_unit_id: int | None = None,
    ) -> dict:
        if date_from > date_to:
            raise ValueError("date_from must be on or before date_to")

        # Commercial profit-and-loss headline figures.
        pnl = FinancialStatementService(self.db).profit_and_loss(
            date_from=date_from, date_to=date_to,
            location_id=location_id, department_id=department_id,
            business_unit_id=business_unit_id,
        )
        laba_bersih_komersial = Decimal(pnl["summary"]["net_profit_before_tax"] or ZERO)

        # Per-commercial posting account balances within the period.
        trial = FinancialStatementService(self.db).trial.report(
            date_from=date_from, date_to=date_to, include_zero_balance=True,
            paginate=False, page_size=10000,
            location_id=location_id, department_id=department_id,
            business_unit_id=business_unit_id,
        )["items"]

        # Build commercial->fiscal mapping lookup.
        mapping_rows = (
            self.db.query(FiscalAccountMapping, FiscalAccount, ChartOfAccount)
            .join(FiscalAccount, FiscalAccountMapping.fiscal_account_id == FiscalAccount.id)
            .join(ChartOfAccount, FiscalAccountMapping.commercial_account_id == ChartOfAccount.id)
            .filter(FiscalAccount.is_active.is_(True))
            .all()
        )
        by_commercial: dict[int, tuple[FiscalAccount, ChartOfAccount]] = {}
        for mapping, fiscal, commercial in mapping_rows:
            by_commercial.setdefault(commercial.id, (fiscal, commercial))

        # Aggregate trial rows into fiscal lines, accumulating corrections.
        lines: dict[int, dict] = {}
        total_komersial = ZERO
        total_koreksi_positif = ZERO
        total_koreksi_negatif = ZERO
        total_fiskal = ZERO
        unmapped: list[dict] = []

        for row in trial:
            if row["account_type"] not in {"REVENUE", "EXPENSE"}:
                continue
            mapped = by_commercial.get(row["account_id"])
            komersial = self._period_amount(row)
            if komersial == ZERO:
                continue
            total_komersial += komersial
            if mapped is None:
                unmapped.append({
                    "commercial_code": row["account_code"],
                    "commercial_name": row["account_name"],
                    "saldo_komersial": komersial,
                })
                continue

            fiscal, commercial = mapped
            klasifikasi = (fiscal.klasifikasi_fiskal or "NORMAL").upper()
            koreksi_positif = ZERO
            koreksi_negatif = ZERO
            fiscal_amount = komersial

            if klasifikasi in ("FINAL", "NON_DEDUCTIBLE", "KOREKSI_POSITIF"):
                # Whole amount removed from fiscal income.
                fiscal_amount = ZERO
                koreksi_negatif = komersial
                total_koreksi_negatif += komersial
            elif klasifikasi == "KOREKSI_NEGATIF":
                koreksi_positif = -komersial
                fiscal_amount = komersial + koreksi_positif
                total_koreksi_positif += koreksi_positif
            else:  # NORMAL
                fiscal_amount = komersial

            total_fiskal += fiscal_amount

            key = fiscal.id
            line = lines.setdefault(key, {
                "fiscal_account_id": fiscal.id,
                "fiscal_code": fiscal.code,
                "fiscal_name": fiscal.name,
                "klasifikasi_fiskal": klasifikasi,
                "saldo_komersial": ZERO,
                "koreksi_positif": ZERO,
                "koreksi_negatif": ZERO,
                "saldo_fiskal": ZERO,
                "accounts": [],
            })
            line["saldo_komersial"] += komersial
            line["koreksi_positif"] += koreksi_positif
            line["koreksi_negatif"] += koreksi_negatif
            line["saldo_fiskal"] += fiscal_amount
            line["accounts"].append({
                "commercial_account_id": commercial.id,
                "commercial_code": commercial.account_number,
                "commercial_name": commercial.account_name,
                "saldo_komersial": komersial,
                "koreksi_positif": koreksi_positif,
                "koreksi_negatif": koreksi_negatif,
                "saldo_fiskal": fiscal_amount,
            })

        lines_list = sorted(
            lines.values(), key=lambda line: (line["fiscal_code"],)
        )
        laba_fiskal = laba_bersih_komersial + total_koreksi_positif + total_koreksi_negatif
        pph_terutang = laba_fiskal * PPH_31E_RATE if laba_fiskal > ZERO else ZERO

        return {
            "date_from": date_from,
            "date_to": date_to,
            "lines": lines_list,
            "unmapped": unmapped,
            "summary": {
                "laba_bersih_komersial": laba_bersih_komersial,
                "total_komersial": total_komersial,
                "koreksi_positif": total_koreksi_positif,
                "koreksi_negatif": total_koreksi_negatif,
                "laba_fiskal_pkp": laba_fiskal,
                "pph_rate": PPH_31E_RATE,
                "pph_terutang": pph_terutang,
            },
            "metadata": {
                "canonical_source": "POSTED_JOURNAL_LINES",
                "basis": "Commercial P&L (net_profit_before_tax) + fiscal corrections",
                "pasal": "Pasal 31E (11%)",
            },
        }
