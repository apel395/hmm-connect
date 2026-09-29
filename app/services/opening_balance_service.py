from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.opening_balance import OpeningBalance
from app.models.location import Location

from app.schemas.journal import JournalCreate, JournalLineCreate

from app.services.audit import record_audit
from app.services.document_number import next_document_number
from app.services.journal_service import JournalService
from app.services.general_ledger import GeneralLedgerService
from app.services.fiscal_period_service import FiscalPeriodService
from app.services.location_access import enforce_location_access, resolve_location_id


ZERO = Decimal("0.00")

BALANCE_SHEET_TYPES = ["ASSET", "LIABILITY", "EQUITY"]

class OpeningBalanceService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def opening_date(fiscal_year: int) -> date:
        return date(fiscal_year, 1, 1)

    def accounts(
        self, *, fiscal_year: int, location_id: int | None
    ) -> dict:
        rows = (
            self.db.query(
                ChartOfAccount.id,
                ChartOfAccount.account_number,
                ChartOfAccount.account_name,
                ChartOfAccount.account_type,
                ChartOfAccount.normal_balance,
                func.coalesce(func.sum(OpeningBalance.amount), 0).label("balance"),
            )
            .outerjoin(
                OpeningBalance,
                (OpeningBalance.account_id == ChartOfAccount.id)
                & (OpeningBalance.fiscal_year == fiscal_year)
                & (OpeningBalance.location_id == location_id),
            )
            .filter(ChartOfAccount.is_active.is_(True))
            .filter(ChartOfAccount.is_posting.is_(True))
            .filter(ChartOfAccount.account_type.in_(BALANCE_SHEET_TYPES))
            .group_by(
                ChartOfAccount.id,
                ChartOfAccount.account_number,
                ChartOfAccount.account_name,
                ChartOfAccount.account_type,
                ChartOfAccount.normal_balance,
            )
            .order_by(ChartOfAccount.account_number)
            .all()
        )
        return {
            "items": [
                {
                    "id": r.id,
                    "account_code": r.account_number,
                    "account_name": r.account_name,
                    "account_type": r.account_type,
                    "normal_balance": r.normal_balance,
                    "existing_balance": Decimal(r.balance or 0),
                }
                for r in rows
            ],
            "count": len(rows),
        }

    def list_entries(self, *, fiscal_year: int, location_id: int | None) -> dict:
        query = (
            self.db.query(OpeningBalance)
            .filter(OpeningBalance.fiscal_year == fiscal_year)
        )
        if location_id:
            query = query.filter(OpeningBalance.location_id == location_id)
        rows = query.order_by(OpeningBalance.id).all()
        journal_ids = {r.journal_entry_id for r in rows if r.journal_entry_id}
        imbalances = []
        if journal_ids:
            journals = self.db.query(JournalEntry).filter(
                JournalEntry.id.in_(journal_ids),
                JournalEntry.status == "POSTED",
                JournalEntry.reference_type == "OPENING_BALANCE",
            ).all()
            for journal in journals:
                difference = sum(
                    (Decimal(line.debit or 0) - Decimal(line.credit or 0) for line in journal.lines),
                    ZERO,
                )
                if difference != ZERO:
                    imbalances.append({
                        "journal_id": journal.id,
                        "journal_number": journal.journal_number,
                        "difference": difference,
                        "location_id": journal.location_id,
                    })
        return {
            "items": [
                {
                    "id": r.id,
                    "account_id": r.account_id,
                    "account_code": r.account.account_number,
                    "account_name": r.account.account_name,
                    "amount": r.amount,
                    "balance_type": r.balance_type,
                    "description": r.description,
                    "journal_entry_id": r.journal_entry_id,
                    "posted_at": r.posted_at,
                }
                for r in rows
            ],
            "count": len(rows),
            "imbalances": imbalances,
            "total_debit": sum(
                (Decimal(r.amount) for r in rows if r.balance_type == "DEBIT"), ZERO
            ),
            "total_credit": sum(
                (Decimal(r.amount) for r in rows if r.balance_type == "CREDIT"), ZERO
            ),
        }

    def prepare(
        self, *, fiscal_year: int, lines: list[dict]
    ) -> dict:
        total_debit = ZERO
        total_credit = ZERO
        ledger_lines = []
        for raw in lines:
            account_id = int(raw.get("account_id") or 0)
            amount = Decimal(raw.get("amount") or 0)
            if amount < 0:
                raise HTTPException(400, "Opening balance amounts cannot be negative")
            if amount == 0:
                continue
            account = self.db.get(ChartOfAccount, account_id)
            if account is None:
                raise HTTPException(404, f"Account {account_id} not found")
            if not account.is_active or not account.is_posting:
                raise HTTPException(
                    400, f"Account {account.account_number} is not an active posting account"
                )
            if account.account_type not in BALANCE_SHEET_TYPES:
                raise HTTPException(
                    400,
                    f"Opening balances only apply to balance-sheet accounts "
                    f"(got {account.account_type} for {account.account_number})",
                )
            balance_type = (raw.get("balance_type") or account.normal_balance).upper()
            if balance_type not in ("DEBIT", "CREDIT"):
                raise HTTPException(400, f"Invalid balance type {balance_type}")
            if balance_type == "DEBIT":
                total_debit += amount
            else:
                total_credit += amount
            ledger_lines.append(
                {
                    "account_id": account_id,
                    "account_code": account.account_number,
                    "balance_type": balance_type,
                    "amount": amount,
                }
            )

        return {
            "lines": ledger_lines,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "difference": abs(total_debit - total_credit),
            "differences_ok": total_debit == total_credit,
        }

    def post(
        self, *, user, fiscal_year: int, location_id: int | None,
        lines: list[dict], description: str | None,
    ) -> dict:
        prepared = self.prepare(fiscal_year=fiscal_year, lines=lines)
        if not prepared["lines"]:
            raise HTTPException(400, "Enter at least one opening balance amount")
        if not prepared["differences_ok"]:
            raise HTTPException(
                400,
                f"Opening balances are not balanced: debit {prepared['total_debit']:.2f}, "
                f"credit {prepared['total_credit']:.2f}. Enter the balancing account "
                "amount manually before posting.",
            )
        posting_date = self.opening_date(fiscal_year)
        resolved_location_id = resolve_location_id(user, location_id)
        if resolved_location_id is None:
            fallback = (
                self.db.query(Location)
                .filter(Location.is_active.is_(True))
                .order_by(Location.id)
                .first()
            )
            if fallback is None:
                raise HTTPException(
                    status_code=400,
                    detail="No active location is available for opening balances",
                )
            resolved_location_id = fallback.id

        # Serialize concurrent annual submissions before checking existing rows.
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": 920000000 + fiscal_year},
            )
        recorded = self.db.query(OpeningBalance.id).filter(
            OpeningBalance.fiscal_year == fiscal_year
        ).first()
        if recorded:
            raise HTTPException(409, f"Opening balances for {fiscal_year} have already been recorded")

        journal_lines = []
        for item in prepared["lines"]:
            if item["balance_type"] == "DEBIT":
                journal_lines.append(
                    JournalLineCreate(
                        account_id=item["account_id"],
                        debit=item["amount"],
                        credit=ZERO,
                        description=description or "Opening Balance",
                    )
                )
            else:
                journal_lines.append(
                    JournalLineCreate(
                        account_id=item["account_id"],
                        debit=ZERO,
                        credit=item["amount"],
                        description=description or "Opening Balance",
                    )
                )

        journal = JournalService.post(
            db=self.db,
            user=user,
            journal=JournalCreate(
                posting_date=posting_date,
                document_type="OPENING_BALANCE",
                document_number=next_document_number(self.db, "OPEN", digits=6),
                reference_type="OPENING_BALANCE",
                reference_id=fiscal_year,
                description=description or f"Opening Balances {fiscal_year}",
                location_id=resolved_location_id,
                lines=journal_lines,
            ),
        )

        for item in prepared["lines"]:
            self.db.add(
                OpeningBalance(
                    fiscal_year=fiscal_year,
                    account_id=item["account_id"],
                    location_id=resolved_location_id,
                    amount=item["amount"],
                    balance_type=item["balance_type"],
                    description=description or "Opening Balance",
                    journal_entry_id=journal.id,
                    posted_by_id=user.id,
                    posted_at=journal.posted_at,
                )
            )

        self.db.flush()
        record_audit(
            self.db, user, "OPENING_BALANCE_POSTED", "OPENING_BALANCE",
            f"Posted opening balances for fiscal year {fiscal_year}",
            entity_id=journal.id, reference_document=journal.document_number,
        )
        self.db.commit()
        return {
            "journal_id": journal.id,
            "journal_number": journal.journal_number,
            "fiscal_year": fiscal_year,
            **prepared,
        }

    def complete_imbalance(
        self, *, user, journal_id: int, lines: list[dict], description: str | None,
    ) -> dict:
        journal = self.db.query(JournalEntry).filter(
            JournalEntry.id == journal_id,
        ).with_for_update().first()
        if (journal is None or journal.status != "POSTED"
                or journal.reference_type != "OPENING_BALANCE"
                or journal.posting_date.year != journal.reference_id):
            raise HTTPException(409, "Posted opening journal not found")
        enforce_location_access(user, journal.location_id)
        if not self.db.query(OpeningBalance.id).filter(
            OpeningBalance.journal_entry_id == journal_id,
        ).first():
            raise HTTPException(409, "Opening journal has no linked opening balances")

        FiscalPeriodService.validate_posting_date(
            db=self.db, posting_date=journal.posting_date,
        )
        previous = sum(
            (Decimal(line.debit or 0) - Decimal(line.credit or 0) for line in journal.lines),
            ZERO,
        )
        if previous == ZERO:
            raise HTTPException(409, "Opening journal is already balanced")
        prepared = self.prepare(fiscal_year=journal.posting_date.year, lines=lines)
        if not prepared["lines"]:
            raise HTTPException(400, "Enter a balancing account amount")
        correction = prepared["total_debit"] - prepared["total_credit"]
        if previous + correction != ZERO:
            raise HTTPException(
                400,
                f"Correction must offset the exact opening difference of {previous:.2f}",
            )

        posted_at = datetime.now(timezone.utc)
        next_line = max((line.line_number or 0 for line in journal.lines), default=0)
        for index, item in enumerate(prepared["lines"], 1):
            debit = item["amount"] if item["balance_type"] == "DEBIT" else ZERO
            credit = item["amount"] if item["balance_type"] == "CREDIT" else ZERO
            self.db.add(JournalLine(
                journal_entry_id=journal.id,
                account_id=item["account_id"],
                debit=debit,
                credit=credit,
                description=description or "Manual opening balance completion",
                line_number=next_line + index,
                location_id=journal.location_id,
                business_unit_id=journal.business_unit_id,
                department_id=journal.department_id,
            ))
            GeneralLedgerService.post(
                db=self.db,
                account_id=item["account_id"],
                debit=debit,
                credit=credit,
                posting_date=journal.posting_date,
                journal_source="JOURNAL",
                document_type=journal.document_type,
                document_number=journal.document_number,
                reference_type=journal.reference_type,
                reference_id=journal.reference_id,
                reference_number=journal.journal_number,
                description=description or "Manual opening balance completion",
                user_id=user.id,
            )
            self.db.add(OpeningBalance(
                fiscal_year=journal.reference_id,
                account_id=item["account_id"],
                location_id=journal.location_id,
                amount=item["amount"],
                balance_type=item["balance_type"],
                description=description or "Manual opening balance completion",
                journal_entry_id=journal.id,
                posted_by_id=user.id,
                posted_at=posted_at,
            ))
        self.db.flush()
        record_audit(
            self.db, user, "OPENING_BALANCE_COMPLETED", "OPENING_BALANCE",
            f"Manually completed opening journal {journal.journal_number}",
            entity_id=journal.id, reference_document=journal.document_number,
            before_data={"debit_credit_difference": str(previous)},
            after_data={"debit_credit_difference": "0.00",
                        "lines": [{**item, "amount": str(item["amount"])} for item in prepared["lines"]]},
        )
        self.db.commit()
        return {
            "journal_id": journal.id,
            "journal_number": journal.journal_number,
            "previous_difference": previous,
            "difference": ZERO,
        }

    def void(self, *, user, fiscal_year: int, location_id: int | None = None) -> dict:
        raise HTTPException(
            409,
            "Recorded opening balances are immutable; use a controlled adjustment journal",
        )
