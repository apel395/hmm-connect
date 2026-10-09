from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.dependencies.authorization import is_superuser
from app.api.v1.organization_dimensions import require_access
from app.models import Base
from app.models.approval_request import ApprovalRequestStep
from app.models.chart_of_account import ChartOfAccount
from app.models.location import Location
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.role import Role
from app.models.user import User
from app.services.approval import (
    LOCAL_APPROVAL_CHAIN,
    MANAGER_APPROVAL_CHAIN,
    MARKET_LIST_APPROVAL_CHAIN,
    WORKFLOW_CHAINS,
    can_user_decide_step,
)
from app.services.financial_statement_service import FinancialStatementService
from app.services.finance_dashboard_service import FinanceDashboardService
from app.services.trial_balance_service import TrialBalanceService


def user_with_role(role_name: str, *, location=None) -> User:
    return User(
        username=role_name.lower().replace(" ", "_"),
        email=f"{role_name.lower().replace(' ', '_')}@example.test",
        full_name=role_name,
        password_hash="x",
        is_active=True,
        roles=[Role(name=role_name)],
        location=location,
    )


def test_only_system_administrator_is_superuser():
    assert is_superuser(user_with_role("SYSTEM_ADMINISTRATOR")) is True
    for role_name in ("ADMIN", "SUPER_ADMIN", "FINANCE_ADMIN", "ERP_ADMINISTRATOR", "HOTEL_ADMINISTRATOR"):
        assert is_superuser(user_with_role(role_name)) is False


def test_organization_dimension_reads_are_authenticated_role_agnostic_and_writes_are_restricted():
    for role_name in ("SYSTEM_ADMINISTRATOR", "PURCHASING", "WAREHOUSE", "FINANCE", "DEPARTMENT"):
        require_access(user_with_role(role_name))
    with pytest.raises(HTTPException) as denied:
        require_access(user_with_role("PURCHASING"), manage=True)
    assert denied.value.status_code == 403
    require_access(user_with_role("SYSTEM_ADMINISTRATOR"), manage=True)


def test_balance_sheet_uses_normalized_closing_balance():
    for normal_balance in ("DEBIT", "CREDIT"):
        assert FinancialStatementService._net(
            {"closing_balance": Decimal("800"), "normal_balance": normal_balance}
        ) == Decimal("800")


def test_approval_chains_match_each_document_flow():
    assert WORKFLOW_CHAINS["PR_APPROVAL"] == LOCAL_APPROVAL_CHAIN
    assert WORKFLOW_CHAINS["ML_APPROVAL"] == MARKET_LIST_APPROVAL_CHAIN
    assert WORKFLOW_CHAINS["RR_APPROVAL"] == (
        (1, "Store Approval", "STORE"),
        (2, "PM / Camp Boss Approval", "PM/CAMP BOSS"),
    )
    assert WORKFLOW_CHAINS["PO_APPROVAL"] == MANAGER_APPROVAL_CHAIN
    assert [step[2] for step in LOCAL_APPROVAL_CHAIN] == ["STORE", "CHEF", "PM/CAMP BOSS"]
    assert [step[2] for step in MARKET_LIST_APPROVAL_CHAIN] == ["CHEF", "PM/CAMP BOSS"]
    assert [step[2] for step in MANAGER_APPROVAL_CHAIN] == ["HO PURCHASING", "FINANCE", "GENERAL MANAGER"]


def test_local_approval_rejects_wrong_location():
    pekanbaru = Location(code="PKU", name="PEKANBARU", location_type="SITE", is_active=True)
    batam = Location(code="BTM", name="BATAM", location_type="SITE", is_active=True)
    step = ApprovalRequestStep(
        step_order=1,
        name="Store Approval",
        approver_role_name="STORE",
        location_name="PEKANBARU",
        status="PENDING",
    )
    assert can_user_decide_step(step, user_with_role("STORE", location=pekanbaru)) is True
    assert can_user_decide_step(step, user_with_role("STORE", location=batam)) is False


def test_trial_balance_excludes_parent_accounts_and_keeps_leaves():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    root = ChartOfAccount(account_number="1000", account_name="ASSET", account_type="ASSET", normal_balance="DEBIT", is_posting=True, is_active=True)
    cash = ChartOfAccount(account_number="1100", account_name="Cash", account_type="ASSET", normal_balance="DEBIT", is_posting=True, is_active=True, parent=root)
    bank_a = ChartOfAccount(account_number="1101", account_name="Bank A", account_type="ASSET", normal_balance="DEBIT", is_posting=True, is_active=True, parent=cash)
    bank_b = ChartOfAccount(account_number="1102", account_name="Bank B", account_type="ASSET", normal_balance="DEBIT", is_posting=True, is_active=True, parent=cash)
    db.add_all([root, cash, bank_a, bank_b])
    db.commit()

    report = TrialBalanceService(db).report(
        date_from=date(2026, 8, 1), date_to=date(2026, 8, 31), include_zero_balance=True
    )
    assert [row["account_code"] for row in report["items"]] == ["1101", "1102"]
    assert TrialBalanceService(db).report(
        date_from=date(2026, 8, 1), date_to=date(2026, 8, 31),
        include_zero_balance=True, search="Bank A",
    )["total_items"] == 1
    db.close()


def test_finance_dashboard_builds_with_empty_optional_modules_and_posted_journal():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    admin = user_with_role("SYSTEM_ADMINISTRATOR")
    db.add(admin)
    accounts = {
        kind: ChartOfAccount(
            account_number=str(index), account_name=kind, account_type=kind,
            normal_balance="DEBIT" if kind in {"ASSET", "EXPENSE"} else "CREDIT",
            financial_statement_group={
                "ASSET": "CURRENT_ASSET", "LIABILITY": "CURRENT_LIABILITY",
                "EQUITY": "EQUITY", "REVENUE": "OPERATING_REVENUE",
                "EXPENSE": "OPERATING_EXPENSE",
            }[kind],
            is_posting=True, is_active=True,
        )
        for index, kind in enumerate(("ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"), 2001)
    }
    journal = JournalEntry(
        journal_number="MAN-TEST", posting_date=date(2026, 8, 10), status="POSTED",
        reference_type="MANUAL", reference_id=1,
        lines=[
            JournalLine(account=accounts["ASSET"], debit=Decimal("1600"), credit=Decimal("0")),
            JournalLine(account=accounts["EXPENSE"], debit=Decimal("100"), credit=Decimal("0")),
            JournalLine(account=accounts["LIABILITY"], debit=Decimal("0"), credit=Decimal("800")),
            JournalLine(account=accounts["EQUITY"], debit=Decimal("0"), credit=Decimal("400")),
            JournalLine(account=accounts["REVENUE"], debit=Decimal("0"), credit=Decimal("500")),
        ],
    )
    db.add(journal)
    db.commit()

    result = FinanceDashboardService(db, admin).build(
        as_of_date=date(2026, 8, 20),
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 20),
    )
    assert result["financial_position"]["total_assets"] == Decimal("1600")
    assert result["financial_position"]["total_liabilities"] == Decimal("800")
    assert result["financial_position"]["total_equity"] == Decimal("800")
    assert result["approvals"]["total_pending_for_me"] == 0
    db.close()
