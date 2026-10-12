from datetime import datetime, timezone
from hashlib import sha256
import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, text
from sqlalchemy.orm import Session

from app.models.chart_of_account import ChartOfAccount
from app.models.opening_balance import OpeningBalance
from app.models.location import Location
from app.models.fiscal_period import FiscalPeriod

from app.services.audit import record_audit
from app.services.location_access import resolve_location_id


ZERO = Decimal("0.00")

BALANCE_SHEET_TYPES = ["ASSET", "LIABILITY", "EQUITY"]

class OpeningBalanceService:
    def __init__(self, db: Session):
        self.db = db

    def _can_edit(self, fiscal_year: int) -> bool:
        return self.db.query(FiscalPeriod.id).filter(
            FiscalPeriod.fiscal_year == fiscal_year,
            FiscalPeriod.is_open.is_(True),
            FiscalPeriod.is_closed.is_(False),
        ).first() is not None

    def _require_open_year(self, fiscal_year: int) -> None:
        if not self._can_edit(fiscal_year):
            raise HTTPException(
                400,
                f"No accounting period in {fiscal_year} is open. Open a period before saving opening balances.",
            )

    @staticmethod
    def _snapshot_version(rows: list[OpeningBalance]) -> str:
        values = [
            (row.id, row.account_id, row.balance_type, str(row.amount), row.location_id)
            for row in rows
        ]
        return sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _snapshot_data(rows: list[OpeningBalance]) -> dict:
        return {
            "lines": [
                {"account_id": row.account_id, "balance_type": row.balance_type,
                 "amount": str(row.amount), "location_id": row.location_id}
                for row in rows
            ],
            "total_debit": str(sum(
                (Decimal(row.amount) for row in rows if row.balance_type == "DEBIT"), ZERO
            )),
            "total_credit": str(sum(
                (Decimal(row.amount) for row in rows if row.balance_type == "CREDIT"), ZERO
            )),
        }

    def _lock_year(self, fiscal_year: int) -> None:
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": 920000000 + fiscal_year},
            )

    def accounts(
        self, *, fiscal_year: int, location_id: int | None, business_unit_id: int | None = None
    ) -> dict:
        join_on = (
            (OpeningBalance.account_id == ChartOfAccount.id)
            & (OpeningBalance.fiscal_year == fiscal_year)
        )
        if location_id is not None:
            join_on = join_on & (OpeningBalance.location_id == location_id)
        if business_unit_id is not None:
            join_on = join_on & OpeningBalance.location_id.in_(
                self.db.query(Location.id).filter(Location.business_unit_id == business_unit_id)
            )
        rows = (
            self.db.query(
                ChartOfAccount.id,
                ChartOfAccount.account_number,
                ChartOfAccount.account_name,
                ChartOfAccount.account_type,
                ChartOfAccount.normal_balance,
                func.coalesce(func.sum(case((OpeningBalance.balance_type == "DEBIT", OpeningBalance.amount), else_=0)), 0).label("debit"),
                func.coalesce(func.sum(case((OpeningBalance.balance_type == "CREDIT", OpeningBalance.amount), else_=0)), 0).label("credit"),
            )
            .outerjoin(OpeningBalance, join_on)
            .filter(or_(
                and_(
                    ChartOfAccount.is_active.is_(True),
                    ChartOfAccount.is_posting.is_(True),
                    ChartOfAccount.account_type.in_(BALANCE_SHEET_TYPES),
                ),
                OpeningBalance.id.isnot(None),
            ))
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
                    "existing_balance": (Decimal(r.debit or 0) - Decimal(r.credit or 0))
                    if r.normal_balance == "DEBIT" else (Decimal(r.credit or 0) - Decimal(r.debit or 0)),
                    "existing_debit": Decimal(r.debit or 0),
                    "existing_credit": Decimal(r.credit or 0),
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
            "can_edit": self._can_edit(fiscal_year),
            "snapshot_version": self._snapshot_version(rows),
        }

    def prepare(
        self, *, fiscal_year: int, lines: list[dict]
    ) -> dict:
        total_debit = ZERO
        total_credit = ZERO
        ledger_lines = []
        seen_accounts = set()
        for raw in lines:
            account_id = int(raw.get("account_id") or 0)
            amount = Decimal(str(raw.get("amount") or 0))
            if amount != amount.quantize(Decimal("0.01")):
                raise HTTPException(400, "Opening balance amounts must have at most two decimals")
            if amount < 0:
                raise HTTPException(400, "Opening balance amounts cannot be negative")
            if amount == 0:
                continue
            account = self.db.get(ChartOfAccount, account_id)
            if account is None:
                raise HTTPException(404, f"Account {account_id} not found")
            historical = self.db.query(OpeningBalance.id).filter(
                OpeningBalance.fiscal_year == fiscal_year,
                OpeningBalance.account_id == account_id,
            ).first() is not None
            if (not account.is_active or not account.is_posting) and not historical:
                raise HTTPException(
                    400, f"Account {account.account_number} is not an active posting account"
                )
            if account.account_type not in BALANCE_SHEET_TYPES and not historical:
                raise HTTPException(
                    400,
                    f"Opening balances only apply to balance-sheet accounts "
                    f"(got {account.account_type} for {account.account_number})",
                )
            balance_type = (raw.get("balance_type") or account.normal_balance).upper()
            if balance_type not in ("DEBIT", "CREDIT"):
                raise HTTPException(400, f"Invalid balance type {balance_type}")
            key = (account_id, balance_type)
            if key in seen_accounts:
                raise HTTPException(400, f"Duplicate opening balance for account {account_id} on {balance_type}")
            seen_accounts.add(key)
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

        # Serialize annual saves before checking the snapshot and period.
        self._lock_year(fiscal_year)
        self._require_open_year(fiscal_year)
        recorded = self.db.query(OpeningBalance.id).filter(
            OpeningBalance.fiscal_year == fiscal_year
        ).first()
        if recorded:
            raise HTTPException(409, f"Opening balances for {fiscal_year} have already been recorded")

        posted_at = datetime.now(timezone.utc)
        created = []
        for item in prepared["lines"]:
            row = OpeningBalance(
                fiscal_year=fiscal_year,
                account_id=item["account_id"],
                location_id=resolved_location_id,
                amount=item["amount"],
                balance_type=item["balance_type"],
                description=description or "Opening Balance",
                posted_by_id=user.id,
                posted_at=posted_at,
            )
            self.db.add(row)
            created.append(row)

        self.db.flush()
        record_audit(
            self.db, user, "OPENING_BALANCE_POSTED", "OPENING_BALANCE",
            f"Posted opening balances for fiscal year {fiscal_year}",
            entity_id=created[0].id, reference_document=f"OPENING-{fiscal_year}",
            after_data={"total_debit": str(prepared["total_debit"]),
                        "total_credit": str(prepared["total_credit"]),
                        "difference": str(prepared["difference"]),
                        "lines": [{**line, "amount": str(line["amount"])} for line in prepared["lines"]]},
        )
        self.db.commit()
        return {
            "fiscal_year": fiscal_year,
            **prepared,
        }

    def revise(
        self, *, user, fiscal_year: int, location_id: int | None,
        lines: list[dict], description: str | None, expected_version: str,
    ) -> dict:
        prepared = self.prepare(fiscal_year=fiscal_year, lines=lines)
        self._lock_year(fiscal_year)
        self._require_open_year(fiscal_year)
        existing = (
            self.db.query(OpeningBalance)
            .filter(OpeningBalance.fiscal_year == fiscal_year)
            .order_by(OpeningBalance.id)
            .with_for_update()
            .all()
        )
        if not existing:
            raise HTTPException(409, "Opening balances have changed. Reload before saving.")
        if self._snapshot_version(existing) != expected_version:
            raise HTTPException(409, "Opening balances have changed. Reload before saving.")

        locations = {row.location_id for row in existing}
        if len(locations) != 1:
            raise HTTPException(409, "Opening balances span multiple locations; revise each location separately.")
        existing_location_id = next(iter(locations))
        requested_location_id = resolve_location_id(user, location_id)
        if requested_location_id is not None and requested_location_id != existing_location_id:
            raise HTTPException(404, "Opening balances not found for this location")

        before = self._snapshot_data(existing)
        original_id = existing[0].id
        for row in existing:
            self.db.delete(row)
        self.db.flush()

        now = datetime.now(timezone.utc)
        created = []
        for item in prepared["lines"]:
            row = OpeningBalance(
                fiscal_year=fiscal_year,
                account_id=item["account_id"],
                location_id=existing_location_id,
                amount=item["amount"],
                balance_type=item["balance_type"],
                description=description or "Opening Balance",
                posted_by_id=user.id,
                posted_at=now,
            )
            self.db.add(row)
            created.append(row)
        self.db.flush()
        record_audit(
            self.db, user, "OPENING_BALANCE_REVISED", "OPENING_BALANCE",
            f"Revised opening balances for fiscal year {fiscal_year}",
            entity_id=created[0].id if created else original_id,
            reference_document=f"OPENING-{fiscal_year}",
            before_data=before,
            after_data=self._snapshot_data(created),
        )
        self.db.commit()
        return {"fiscal_year": fiscal_year, **prepared}

    def void(self, *, user, fiscal_year: int, location_id: int | None = None) -> dict:
        raise HTTPException(
            409,
            "Recorded opening balances are immutable; use an audited opening-balance revision",
        )
