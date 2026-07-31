from sqlalchemy.orm import Session

from app.models.chart_of_account import ChartOfAccount


DEFAULT_CHART_OF_ACCOUNTS = [

    {
        "account_number": "1000",
        "account_name": "Cash",
        "account_type": "ASSET",
        "normal_balance": "DEBIT",
        "cash_flow_category": "OPERATING",
        "is_posting": True,
        "is_system": True,
    },

    {
        "account_number": "1010",
        "account_name": "Bank",
        "account_type": "ASSET",
        "normal_balance": "DEBIT",
        "cash_flow_category": "OPERATING",
        "is_posting": True,
        "is_system": True,
    },

    {
        "account_number": "1100",
        "account_name": "Inventory",
        "account_type": "ASSET",
        "normal_balance": "DEBIT",
        "cash_flow_category": None,
        "is_posting": True,
        "is_system": True,
    },

    {
        "account_number": "1200",
        "account_name": "Accounts Receivable",
        "account_type": "ASSET",
        "normal_balance": "DEBIT",
        "cash_flow_category": "OPERATING",
        "is_posting": True,
        "is_system": True,
    },

    {
        "account_number": "2100",
        "account_name": "Accounts Payable",
        "account_type": "LIABILITY",
        "normal_balance": "CREDIT",
        "cash_flow_category": "OPERATING",
        "is_posting": True,
        "is_system": True,
    },

    {
        "account_number": "3100",
        "account_name": "Owner Capital",
        "account_type": "EQUITY",
        "normal_balance": "CREDIT",
        "cash_flow_category": None,
        "is_posting": True,
        "is_system": True,
    },

    {
        "account_number": "4100",
        "account_name": "Sales Revenue",
        "account_type": "REVENUE",
        "normal_balance": "CREDIT",
        "cash_flow_category": "OPERATING",
        "is_posting": True,
        "is_system": True,
    },

    {
        "account_number": "5100",
        "account_name": "Purchase Expense",
        "account_type": "EXPENSE",
        "normal_balance": "DEBIT",
        "cash_flow_category": "OPERATING",
        "is_posting": True,
        "is_system": True,
    },

    {
        "account_number": "6100",
        "account_name": "Salary Expense",
        "account_type": "EXPENSE",
        "normal_balance": "DEBIT",
        "cash_flow_category": "OPERATING",
        "is_posting": True,
        "is_system": True,
    },

    {
        "account_number": "7100",
        "account_name": "Rent Expense",
        "account_type": "EXPENSE",
        "normal_balance": "DEBIT",
        "cash_flow_category": "OPERATING",
        "is_posting": True,
        "is_system": True,
    },

]


def seed_chart_of_accounts(db: Session):

    for item in DEFAULT_CHART_OF_ACCOUNTS:

        exists = (
            db.query(ChartOfAccount)
            .filter(
                ChartOfAccount.account_number == item["account_number"]
            )
            .first()
        )

        if exists:
            continue

        db.add(
            ChartOfAccount(**item)
        )

    db.commit()
