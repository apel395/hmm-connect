from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine

from app.schemas.journal import JournalCreate

from app.services.general_ledger import GeneralLedgerService
from app.services.fiscal_period_service import FiscalPeriodService


ZERO = Decimal("0.00")


class JournalService:

    @staticmethod
    def generate_number(db: Session) -> str:
        count = db.query(JournalEntry).count() + 1
        return f"JV-{count:08d}"

    @classmethod
    def post(
        cls,
        *,
        db: Session,
        journal: JournalCreate,
        user,
        allow_unbalanced_opening: bool = False,
    ) -> JournalEntry:

        if not journal.lines:
            raise HTTPException(
                status_code=400,
                detail="Journal must contain at least one line.",
            )

        if journal.location_id is None:
            raise HTTPException(
                status_code=409,
                detail="Journal requires a work location before posting.",
            )

        total_debit = ZERO
        total_credit = ZERO

        for line in journal.lines:

            debit = Decimal(line.debit)
            credit = Decimal(line.credit)

            if debit < ZERO:
                raise HTTPException(
                    status_code=400,
                    detail="Debit cannot be negative.",
                )

            if credit < ZERO:
                raise HTTPException(
                    status_code=400,
                    detail="Credit cannot be negative.",
                )

            if debit > ZERO and credit > ZERO:
                raise HTTPException(
                    status_code=400,
                    detail="A journal line cannot contain both debit and credit.",
                )

            if debit == ZERO and credit == ZERO:
                raise HTTPException(
                    status_code=400,
                    detail="A journal line must contain a debit or credit amount.",
                )

            total_debit += debit
            total_credit += credit

        if total_debit != total_credit and not (
            allow_unbalanced_opening
            and journal.reference_type in ("OPENING_BALANCE", "OPENING_BALANCE_ADJUSTMENT")
        ):
            raise HTTPException(
                status_code=400,
                detail="Journal is not balanced.",
            )

        FiscalPeriodService.validate_posting_date(
            db=db,
            posting_date=journal.posting_date,
        )

        entry = JournalEntry(
            journal_number=cls.generate_number(db),
            posting_date=journal.posting_date,
            status="POSTED",
            document_type=journal.document_type,
            document_number=journal.document_number,
            reference_type=journal.reference_type,
            reference_id=journal.reference_id,
            description=journal.description,
            created_by_id=user.id,
            posted_by_id=user.id,
            business_unit_id=journal.business_unit_id,
            location_id=journal.location_id,
            department_id=journal.department_id,
        )

        db.add(entry)
        db.flush()

        for item in journal.lines:

            line = JournalLine(
                journal_entry_id=entry.id,
                account_id=item.account_id,
                debit=item.debit,
                credit=item.credit,
                description=item.description,
                business_unit_id=journal.business_unit_id,
                location_id=journal.location_id,
                department_id=item.department_id or journal.department_id,
                supplier_id=item.supplier_id,
            )

            db.add(line)

            GeneralLedgerService.post(
                db=db,
                account_id=item.account_id,
                debit=item.debit,
                credit=item.credit,
                posting_date=journal.posting_date,
                journal_source="JOURNAL",
                document_type=journal.document_type,
                document_number=journal.document_number,
                reference_type=journal.reference_type,
                reference_id=journal.reference_id,
                reference_number=entry.journal_number,
                description=item.description,
                user_id=user.id,
            )

        db.flush()

        return entry