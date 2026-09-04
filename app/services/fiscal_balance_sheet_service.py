from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.chart_of_account import ChartOfAccount
from app.models.fiscal_account import FiscalAccount, FiscalAccountMapping
from app.services.trial_balance_service import TrialBalanceService, ZERO


# Coretax Lampiran L1 (Neraca / Laporan Posisi Keuangan) ordered line-item template.
# Codes mirror PER-11/PJ/2025. "subtotal" entries are computed from their lines.
BALANCE_SHEET_TEMPLATE = {
    "aset": {
        "label": "Assets",
        "sections": [
            {
                "code": "HDR-360",
                "label": "Current Assets",
                "accounts": [
                    "1101", "1122", "1123", "1124", "1125", "1131", "1181",
                    "1200", "1401", "1421", "1422", "1423", "1499",
                ],
            },
            {
                "code": "HDR-374",
                "label": "Non-current Assets",
                "accounts": [
                    "1501", "1521", "1522", "1551", "1599", "1600", "1601",
                    "1611", "1651", "1658", "1698",
                ],
            },
        ],
        "total": "1700",
    },
    "kewajiban_ekuitas": {
        "label": "Liabilities & Equity",
        "sections": [
            {
                "code": "HDR-387",
                "label": "Current Liabilities",
                "accounts": [
                    "2102", "2103", "2111", "2186", "2187", "2191", "2192",
                    "2195", "2201", "2202", "2203", "2228",
                ],
            },
            {
                "code": "HDR-400",
                "label": "Non-current Liabilities",
                "accounts": [
                    "2301", "2303", "2304", "2312", "2321", "2322", "2998",
                ],
            },
            {
                "code": "HDR-409",
                "label": "Equity",
                "accounts": [
                    "3102", "3120", "3200", "3297", "3298",
                ],
            },
        ],
        "total": "3300",
    },
}


class FiscalBalanceSheetService:
    def __init__(self, db: Session):
        self.db = db
        self.trial = TrialBalanceService(db)

    def _closing_balances(self, fiscal_year: int, *, location_id=None, department_id=None) -> dict[int, Decimal]:
        """Closing (Saldo Akhir) normal-balance-adjusted balance per posting account."""
        as_of = date(fiscal_year, 12, 31)
        rows = self.trial.report(
            date_from=date(fiscal_year, 1, 1), date_to=as_of,
            include_zero_balance=True, paginate=False, page_size=1000,
            location_id=location_id, department_id=department_id,
        )["items"]
        return {row["account_id"]: Decimal(row["closing_balance"]) for row in rows}

    def report(self, *, fiscal_year: int, location_id=None, department_id=None) -> dict:
        closing = self._closing_balances(fiscal_year, location_id=location_id, department_id=department_id)

        # fiscal code -> fiscal account (active, balance-sheet categories only for rollup)
        rows = (
            self.db.query(FiscalAccount)
            .filter(FiscalAccount.is_active.is_(True))
            .filter(FiscalAccount.category.in_(["Aset", "Kewajiban", "Modal"]))
            .all()
        )
        fiscal_by_code = {f.code: f for f in rows}

        # commercial account id -> fiscal code
        mapping_rows = (
            self.db.query(FiscalAccountMapping, FiscalAccount)
            .join(FiscalAccount, FiscalAccountMapping.fiscal_account_id == FiscalAccount.id)
            .filter(FiscalAccount.category.in_(["Aset", "Kewajiban", "Modal"]))
            .all()
        )
        commercial_to_fiscal: dict[int, str] = {}
        for mapping, fiscal in mapping_rows:
            commercial_to_fiscal[mapping.commercial_account_id] = fiscal.code

        # rollup: fiscal code -> sum of closing balances of mapped commercial accounts
        fiscal_totals: dict[str, Decimal] = {}
        for commercial_id, balance in closing.items():
            code = commercial_to_fiscal.get(commercial_id)
            if code is None:
                continue
            fiscal_totals[code] = fiscal_totals.get(code, ZERO) + balance

        def build_section(section_spec):
            lines = []
            for code in section_spec["accounts"]:
                fa = fiscal_by_code.get(code)
                amount = fiscal_totals.get(code, ZERO)
                lines.append({
                    "fiscal_code": code,
                    "account_name": fa.name if fa else code,
                    "amount": amount,
                })
            total = sum((line["amount"] for line in lines), ZERO)
            return {
                "code": section_spec["code"],
                "label": section_spec["label"],
                "lines": lines,
                "total": total,
            }

        aset_sections = [build_section(s) for s in BALANCE_SHEET_TEMPLATE["aset"]["sections"]]
        ke_sections = [build_section(s) for s in BALANCE_SHEET_TEMPLATE["kewajiban_ekuitas"]["sections"]]

        total_aset = sum((s["total"] for s in aset_sections), ZERO)
        total_liabilitas = sum((s["total"] for s in ke_sections[:2]), ZERO)
        total_ekuitas = ke_sections[2]["total"]
        total_liab_ekuitas = total_liabilitas + total_ekuitas
        difference = total_aset - total_liab_ekuitas

        return {
            "fiscal_year": fiscal_year,
            "year_start": date(fiscal_year, 1, 1),
            "year_end": date(fiscal_year, 12, 31),
            "sections": [
                {
                    "code": "ASET",
                    "label": "Assets",
                    "sections": aset_sections,
                    "total": total_aset,
                },
                {
                    "code": "KEWAJIBAN_EKUITAS",
                    "label": "Liabilities & Equity",
                    "sections": ke_sections,
                    "total": total_liab_ekuitas,
                },
            ],
            "summary": {
                "total_assets": total_aset,
                "total_liabilities": total_liabilitas,
                "total_equity": total_ekuitas,
                "total_liabilities_and_equity": total_liab_ekuitas,
                "difference": difference,
                "is_balanced": difference == ZERO,
                "mapped_account_count": len(commercial_to_fiscal),
            },
            "metadata": {
                "canonical_source": "POSTED_JOURNAL_LINES",
                "basis": "PER-11/PJ/2025 Lampiran 1 - Laporan Posisi Keuangan (Neraca)",
                "year_start": date(fiscal_year, 1, 1),
                "year_end": date(fiscal_year, 12, 31),
            },
        }
