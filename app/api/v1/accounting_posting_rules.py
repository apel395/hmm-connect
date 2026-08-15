from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.authorization import has_any_role
from app.models.accounting_posting_rule import AccountingPostingRule
from app.schemas.accounting_posting_rule import PostingRuleCreate, PostingRuleUpdate
from app.services.accounting_posting_rule_service import AccountingPostingRuleService
from app.services.audit import record_audit

router = APIRouter(prefix="/accounting/posting-rules", tags=["Accounting Posting Rules"])


def access(user):
    if not has_any_role(user, "FINANCE"):
        raise HTTPException(403, "Finance access required")


@router.get("")
def list_rules(db: Session = Depends(get_db), _=Depends(get_current_user)):
    svc = AccountingPostingRuleService(db)
    return [svc.serialize(x) for x in db.query(AccountingPostingRule).order_by(AccountingPostingRule.event_type).all()]


@router.get("/{rule_id}")
def get_rule(rule_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    row = db.get(AccountingPostingRule, rule_id)
    if not row:
        raise HTTPException(404, "Posting rule not found")
    return AccountingPostingRuleService.serialize(row)


@router.post("", status_code=201)
def create_rule(data: PostingRuleCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    svc = AccountingPostingRuleService(db)
    svc.validate(
        data.debit_account_id,
        data.credit_account_id,
        data.event_type,
        active=data.is_active,
        input_vat_account_id=data.input_vat_account_id,
    )
    row = AccountingPostingRule(**data.model_dump(), created_by_id=user.id)
    db.add(row)
    db.flush()
    record_audit(db, user, "POSTING_RULE_CREATED", "ACCOUNTING_POSTING_RULE", f"Created {row.event_type}", entity_id=row.id)
    db.commit()
    db.refresh(row)
    return svc.serialize(row)


@router.patch("/{rule_id}")
def update_rule(rule_id: int, data: PostingRuleUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    access(user)
    row = db.get(AccountingPostingRule, rule_id)
    if not row:
        raise HTTPException(404, "Posting rule not found")
    values = data.model_dump(exclude_unset=True)
    debit = values.get("debit_account_id", row.debit_account_id)
    credit = values.get("credit_account_id", row.credit_account_id)
    vat = values.get("input_vat_account_id", row.input_vat_account_id)
    event = values.get("event_type", row.event_type)
    active = values.get("is_active", row.is_active)
    AccountingPostingRuleService(db).validate(
        debit,
        credit,
        event,
        row.id,
        active,
        input_vat_account_id=vat,
    )
    for key, value in values.items():
        setattr(row, key, value)
    record_audit(db, user, "POSTING_RULE_UPDATED", "ACCOUNTING_POSTING_RULE", f"Updated {row.event_type}", entity_id=row.id)
    db.commit()
    db.refresh(row)
    return AccountingPostingRuleService.serialize(row)


def toggle(rule_id: int, active: bool, db, user):
    access(user)
    row = db.get(AccountingPostingRule, rule_id)
    if not row:
        raise HTTPException(404, "Posting rule not found")
    if active:
        AccountingPostingRuleService(db).validate(
            row.debit_account_id,
            row.credit_account_id,
            row.event_type,
            row.id,
            True,
            input_vat_account_id=row.input_vat_account_id,
        )
    row.is_active = active
    action = "POSTING_RULE_RESTORED" if active else "POSTING_RULE_ARCHIVED"
    record_audit(db, user, action, "ACCOUNTING_POSTING_RULE", f"{action.split('_')[-1].title()} {row.event_type}", entity_id=row.id)
    db.commit()
    db.refresh(row)
    return AccountingPostingRuleService.serialize(row)


@router.patch("/{rule_id}/archive")
def archive(rule_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return toggle(rule_id, False, db, user)


@router.patch("/{rule_id}/restore")
def restore(rule_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return toggle(rule_id, True, db, user)
