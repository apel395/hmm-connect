from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.chart_of_account import ChartOfAccount
from app.models.accounting_setting import AccountingSetting
from app.models.journal_entry import JournalEntry
from app.models.opening_balance import OpeningBalance

from app.schemas.journal import JournalCreate, JournalLineCreate

from app.services.audit import record_audit
from app.services.document_number import next_document_number
from app.services.journal_service import JournalService
from app.services.location_access import resolve_location_id


ZERO = Decimal("0.00")

BALANCE_SHEET_TYPES = ["ASSET", "LIABILITY", "EQUITY"]

DEFAULT_EQUITY_SETTING_KEY = "OPENING_BALANCE_EQUITY_ACCOUNT"


class OpeningBalanceService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def opening_date(fiscal_year: int) -> date:
        return date(fiscal_year, 1, 1)

    def resolve_equity_account(self) -> ChartOfAccount:
        setting = (
            self.db.query(AccountingSetting)
            .filter(AccountingSetting.setting_key == DEFAULT_EQUITY_SETTING_KEY)
            .first()
        )
        if setting:
            account = self.db.get(ChartOfAccount, setting.account_id)
            if account:
                return account
        account = (
            self.db.query(ChartOfAccount)
            .filter(ChartOfAccount.is_active.is_(True))
            .filter(ChartOfAccount.is_posting.is_(True))
            .filter(ChartOfAccount.account_type == "EQUITY")
            .order_by(ChartOfAccount.account_number)
            .first()
        )
        if account is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Opening Balance Equity account not configured and no "
                    "active posting equity account exists. Set the "
                    f"'{DEFAULT_EQUITY_SETTING_KEY}' accounting setting."
                ),
            )
        return account

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

        equity = self.resolve_equity_account()
        difference = total_debit - total_credit
        contra_type = "CREDIT" if difference >= 0 else "DEBIT"
        ledger_lines.append(
            {
                "contra": True,
                "account_id": equity.id,
                "account_code": equity.account_number,
                "balance_type": contra_type,
                "amount": abs(difference),
            }
        )

        total_debit += abs(difference) if contra_type == "DEBIT" else ZERO
        total_credit += abs(difference) if contra_type == "CREDIT" else ZERO

        return {
            "lines": ledger_lines,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "difference": abs(difference),
            "differences_ok": total_debit == total_credit,
            "equity_account": {
                "id": equity.id,
                "account_code": equity.account_number,
                "account_name": equity.account_name,
            },
        }

    def post(
        self, *, user, fiscal_year: int, location_id: int | None,
        lines: list[dict], description: str | None,
    ) -> dict:
        prepared = self.prepare(fiscal_year=fiscal_year, lines=lines)
        posting_date = self.opening_date(fiscal_year)
        resolved_location_id = resolve_location_id(user, location_id)

        journal_lines = []
        for item in prepared["lines"]:
            is_contra = item.get("contra", False)
            if item["balance_type"] == "DEBIT":
                journal_lines.append(
                    JournalLineCreate(
                        account_id=item["account_id"],
                        debit=item["amount"],
                        credit=ZERO,
                        description="Opening Balance Contra" if is_contra else (
                            description or "Opening Balance"
                        ),
                    )
                )
            else:
                journal_lines.append(
                    JournalLineCreate(
                        account_id=item["account_id"],
                        debit=ZERO,
                        credit=item["amount"],
                        description="Opening Balance Contra" if is_contra else (
                            description or "Opening Balance"
                        ),
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
                    description="Opening Balance Contra" if item.get("contra") else (
                        description or "Opening Balance"
                    ),
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

    def void(self, *, user, fiscal_year: int, location_id: int | None = None) -> dict:
        query = self.db.query(OpeningBalance).filter(
            OpeningBalance.fiscal_year == fiscal_year,
        )
        if location_id:
            query = query.filter(OpeningBalance.location_id == location_id)
        entries = query.all()
        if not entries:
            raise HTTPException(404, f"No opening balances found for {fiscal_year}")
        journal_ids = {e.journal_entry_id for e in entries if e.journal_entry_id}
        for journal_id in journal_ids:
            journal = self.db.get(JournalEntry, journal_id)
            if journal and journal.status == "POSTED":
                from app.services.accounting_unpost import unpost_journal
                unpost_journal(self.db, journal=journal, user=user, commit=False)
        for entry in entries:
            self.db.delete(entry)
        record_audit(
            self.db, user, "OPENING_BALANCE_VOIDED", "OPENING_BALANCE",
            f"Voided opening balances for fiscal year {fiscal_year}",
        )
        self.db.commit()
        return {"voided": len(entries)}
