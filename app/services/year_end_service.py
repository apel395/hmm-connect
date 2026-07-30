from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.chart_of_account import ChartOfAccount
from app.models.fiscal_year_close import FiscalYearClose
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine

from app.schemas.journal import (
    JournalCreate,
    JournalLineCreate,
)

# from app.services.accounting_setting_service import AccountingSettingService
from app.services.journal_service import JournalService


class YearEndService:

    @classmethod
    def close_year(
        cls,
        *,
        db: Session,
        fiscal_year: int,
        closing_date,
        user,
    ):

        exists = (
            db.query(FiscalYearClose)
            .filter(
                FiscalYearClose.fiscal_year == fiscal_year,
            )
            .first()
        )

        if exists:
            raise HTTPException(
                status_code=400,
                detail="Fiscal year already closed.",
            )

        rows = (
            db.query(
                ChartOfAccount.id,
                ChartOfAccount.account_type,
                func.sum(JournalLine.debit).label("debit"),
                func.sum(JournalLine.credit).label("credit"),
            )
            .join(
                JournalLine,
                JournalLine.account_id == ChartOfAccount.id,
            )
            .join(
                JournalEntry,
                JournalEntry.id == JournalLine.journal_entry_id,
            )
            .filter(
                JournalEntry.fiscal_year == fiscal_year,
                ChartOfAccount.account_type.in_(
                    [
                        "REVENUE",
                        "EXPENSE",
                    ]
                ),
            )
            .group_by(
                ChartOfAccount.id,
                ChartOfAccount.account_type,
            )
            .all()
        )

        lines = []

        net_profit = Decimal("0.00")

        for row in rows:

            if row.account_type == "REVENUE":

                amount = Decimal(row.credit or 0) - Decimal(row.debit or 0)

                if amount != 0:

                    lines.append(
                        JournalLineCreate(
                            account_id=row.id,
                            debit=amount,
                            credit=Decimal("0"),
                            description="Year End Closing",
                        )
                    )

                    net_profit += amount

            else:

                amount = Decimal(row.debit or 0) - Decimal(row.credit or 0)

                if amount != 0:

                    lines.append(
                        JournalLineCreate(
                            account_id=row.id,
                            debit=Decimal("0"),
                            credit=amount,
                            description="Year End Closing",
                        )
                    )

                    net_profit -= amount

        retained = 3200

        if net_profit >= 0:

            lines.append(
                JournalLineCreate(
                    account_id=retained,
                    debit=Decimal("0"),
                    credit=net_profit,
                    description="Transfer Net Profit",
                )
            )

        else:

            lines.append(
                JournalLineCreate(
                    account_id=retained,
                    debit=abs(net_profit),
                    credit=Decimal("0"),
                    description="Transfer Net Loss",
                )
            )

        journal = JournalService.post(
            db=db,
            user=user,
            journal=JournalCreate(
                posting_date=closing_date,
                document_type="YEAR_END",
                document_number=f"YE-{fiscal_year}",
                reference_type="YEAR_END",
                reference_id=fiscal_year,
                description=f"Year End Closing {fiscal_year}",
                lines=lines,
            ),
        )

        db.add(
            FiscalYearClose(
                fiscal_year=fiscal_year,
                closing_date=closing_date,
                journal_entry_id=journal.id,
            )
        )

        db.commit()

        return journal
