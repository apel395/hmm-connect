from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.accounting_posting_rule import AccountingPostingRule
from app.models.chart_of_account import ChartOfAccount

class AccountingPostingRuleService:
    def __init__(self, db: Session): self.db = db
    def validate(self, debit_id: int, credit_id: int, event_type: str, exclude_id: int | None = None, active: bool = True):
        if debit_id == credit_id: raise HTTPException(400, "Debit and credit accounts must be different")
        for account_id in (debit_id, credit_id):
            account = self.db.get(ChartOfAccount, account_id)
            if not account or not account.is_active or not account.is_posting: raise HTTPException(400, "Posting rules require active posting accounts")
        query = self.db.query(AccountingPostingRule).filter(AccountingPostingRule.event_type == event_type, AccountingPostingRule.is_active.is_(True))
        if exclude_id: query = query.filter(AccountingPostingRule.id != exclude_id)
        if active and query.first(): raise HTTPException(409, "An active posting rule already exists for this event type")
    @staticmethod
    def serialize(row):
        return {"id":row.id,"event_type":row.event_type,"debit_account_id":row.debit_account_id,"debit_account_code":row.debit_account.account_number,"debit_account_name":row.debit_account.account_name,"credit_account_id":row.credit_account_id,"credit_account_code":row.credit_account.account_number,"credit_account_name":row.credit_account.account_name,"description":row.description,"is_active":row.is_active,"created_at":row.created_at,"updated_at":row.updated_at}
