from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.chart_of_account import ChartOfAccount

from app.models.general_ledger import GeneralLedger
from app.services.document_number import next_document_number
from app.services.fiscal_period_service import FiscalPeriodService


class GeneralLedgerService:

    @staticmethod
    def generate_number(db: Session) -> str:
        # Ledger rows can be deleted by a controlled journal unpost. Counting
        # rows would then reuse an existing GL number on repost. Reuse the
        # transactional document-sequence allocator instead so numbering stays
        # monotonic and concurrency-safe even after deletions.
        return next_document_number(db, "GL", digits=8)

    @staticmethod
    def post(
        db: Session,
        *,
        account_id: int,
        debit: Decimal = Decimal("0.00"),
        credit: Decimal = Decimal("0.00"),
        reference_type: str,
        reference_id: int,
        reference_number: str,
        description: str | None,
        user_id: int,
        posting_date: date | None = None,
        journal_source: str | None = None,
        document_type: str | None = None,
        document_number: str | None = None,
        system_closing: bool = False,
    ) -> GeneralLedger:

        account = db.get(ChartOfAccount, account_id)
        if account and account.account_type in {"REVENUE", "INCOME"} and account.account_number != "400" and reference_type not in {"PERIOD_CLOSE", "YEAR_END"}:
            raise HTTPException(422, "Revenue postings must use account 400")

        if posting_date is None:
            posting_date = date.today()

        FiscalPeriodService.validate_posting_date(
            db=db,
            posting_date=posting_date,
            system_closing=system_closing,
        )

        # Replace this with FiscalPeriodService.get_period(...) if available.
        fiscal_year = posting_date.year
        fiscal_period = posting_date.month

        entry = GeneralLedger(
            journal_number=GeneralLedgerService.generate_number(db),
            posting_date=posting_date,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            account_id=account_id,
            debit=debit,
            credit=credit,
            journal_source=journal_source,
            document_type=document_type,
            document_number=document_number,
            reference_type=reference_type,
            reference_id=reference_id,
            reference_number=reference_number,
            description=description,
            created_by_id=user_id,
        )

        db.add(entry)
        db.flush()

        return entry
