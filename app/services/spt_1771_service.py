from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.tax import CompanyTaxProfile, TaxCredit
from app.models.fiscal_account import FiscalAccount
from app.services.financial_statement_service import FinancialStatementService
from app.services.fiscal_reconciliation_service import (
    FiscalReconciliationService,
    PPH_31E_RATE,
)
from app.services.trial_balance_service import ZERO


class SPT1771Service:
    """Assemble the annual corporate income tax return (SPT Tahunan 1771).

    Sections I-A (commercial profit & loss), II (fiscal reconciliation) and
    III (corporate income tax computation) are derived from the posted journal
    trial balance through the commercial->fiscal COA mapping. Tax credit
    prepayments (PPh 22/23/24/25) and the company tax identity are read from
    the profiles and credits tables keyed by tax year.
    """

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _period(date_from: date, date_to: date) -> tuple[date, date]:
        return (date_from, date_to)

    def report(
        self,
        *,
        tax_year: int,
        location_id: int | None = None,
        department_id: int | None = None,
        business_unit_id: int | None = None,
        kompensasi_kerugian: Decimal | None = None,
    ) -> dict:
        date_from, date_to = date(tax_year, 1, 1), date(tax_year, 12, 31)

        # Commercial profit & loss breakdown (Lampiran I-A).
        pnl = FinancialStatementService(self.db).profit_and_loss(
            date_from=date_from, date_to=date_to,
            location_id=location_id, department_id=department_id,
            business_unit_id=business_unit_id,
        )["summary"]

        # Fiscal reconciliation (Lampiran II).
        recon = FiscalReconciliationService(self.db).report(
            date_from=date_from, date_to=date_to,
            location_id=location_id, department_id=department_id,
            business_unit_id=business_unit_id,
        )
        recon_summary = recon["summary"]

        # P&L line items.
        peredaran_usaha = Decimal(pnl.get("total_revenue") or ZERO) - Decimal(pnl.get("other_revenue") or ZERO)
        total_penghasilan_bruto = Decimal(peredaran_usaha) + Decimal(pnl.get("other_revenue") or ZERO)
        hpp = Decimal(pnl.get("cost_of_revenue") or ZERO)
        laba_kotor = Decimal(pnl.get("gross_profit") or ZERO)
        biaya_usaha = Decimal(pnl.get("operating_expenses") or ZERO)
        laba_usaha = Decimal(pnl.get("operating_profit") or ZERO)
        penghasilan_luar_usaha = Decimal(pnl.get("other_revenue") or ZERO)
        biaya_luar_usaha = Decimal(pnl.get("other_expenses") or ZERO)

        # Fiscal reconciliation figures.
        laba_fiskal = recon_summary["laba_fiskal_pkp"]
        kompensasi = Decimal(kompensasi_kerugian or ZERO)
        if kompensasi < ZERO:
            raise ValueError("kompensasi_kerugian cannot be negative")
        kompensasi = min(kompensasi, laba_fiskal) if laba_fiskal > ZERO else ZERO
        pkp = laba_fiskal - kompensasi
        pph_terutang = Decimal(recon_summary["pph_terutang"])

        # Tax credits (kredit pajak) by type for the year.
        credits = self.db.query(TaxCredit).filter(TaxCredit.tax_year == tax_year).all()
        kredit_by_type: dict[str, Decimal] = {}
        total_kredit = ZERO
        for credit in credits:
            total_kredit += credit.amount
            kredit_by_type[credit.credit_type] = kredit_by_type.get(credit.credit_type, ZERO) + credit.amount
        kredit_total = {k: v for k, v in sorted(kredit_by_type.items())}

        # PPh payable / overpayment.
        pph_kurang_bayar = pph_terutang - total_kredit
        is_lebih_bayar = pph_kurang_bayar < ZERO

        # Company tax identity (Lampiran header).
        profile = self.db.query(CompanyTaxProfile).filter(CompanyTaxProfile.tax_year == tax_year).first()

        return {
            "tax_year": tax_year,
            "date_from": date_from,
            "date_to": date_to,
            "profile": {
                "npwp": profile.npwp if profile else None,
                "company_name": profile.company_name if profile else None,
                "address": profile.address if profile else None,
                "city": profile.city if profile else None,
                "klu": profile.klu if profile else None,
                "phone": profile.phone if profile else None,
                "email": profile.email if profile else None,
                "representative_name": profile.representative_name if profile else None,
            },
            "section_i_a": {
                "peredaran_usaha": peredaran_usaha,
                "penghasilan_luar_usaha": penghasilan_luar_usaha,
                "total_penghasilan_bruto": total_penghasilan_bruto,
                "harga_pokok_penjualan": hpp,
                "laba_kotor_usaha": laba_kotor,
                "biaya_usaha": biaya_usaha,
                "laba_usaha": laba_usaha,
                "penghasilan_neto_luar_negeri": ZERO,
                "biaya_luar_usaha": biaya_luar_usaha,
                "laba_sebelum_pajak": recon_summary["laba_bersih_komersial"],
            },
            "section_ii": {
                "laba_fiskal": laba_fiskal,
                "koreksi_fiskal_positif": recon_summary["koreksi_positif"],
                "koreksi_fiskal_negatif": recon_summary["koreksi_negatif"],
                "kompensasi_kerugian": kompensasi,
                "penghasilan_kena_pajak": pkp,
            },
            "section_iii": {
                "pph_rate": PPH_31E_RATE,
                "pph_terutang": pph_terutang,
                "kredit_pajak": kredit_total,
                "total_kredit_pajak": total_kredit,
                "pph_kurang_bayar": pph_kurang_bayar,
                "pph_lebih_bayar": abs(pph_kurang_bayar) if is_lebih_bayar else ZERO,
                "is_lebih_bayar": is_lebih_bayar,
            },
            "corrections_detail": recon["lines"],
            "unmapped": recon["unmapped"],
            "metadata": {
                "canonical_source": "POSTED_JOURNAL_LINES",
                "pasal": "Pasal 31E (11%)",
            },
        }
