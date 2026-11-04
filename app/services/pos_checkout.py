"""Configured Hotel F&B discounts and payment accounts; no default policy invention."""
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from app.models.accounting_setting import AccountingSetting
from app.models.chart_of_account import ChartOfAccount
from app.models.pos_operations import PosOutletPolicy
from app.schemas.pos_checkout import CheckoutConfiguration
from app.services import pos_operations as ops

METHOD_KEYS = {"CASH":"POS_CASH_ACCOUNT", "CARD":"POS_CARD_ACCOUNT", "BANK_TRANSFER":"POS_TRANSFER_ACCOUNT"}
MONEY = Decimal(".01")


def applies(db, transaction):
    return transaction.transaction_type == "POS" and ops.is_hotel_outlet(db, transaction)


def account(db, account_id):
    row = db.get(ChartOfAccount, account_id) if account_id else None
    if not row or not row.is_active or not row.is_posting or row.account_type != "ASSET" or row.normal_balance != "DEBIT":
        raise HTTPException(422, "Choose an active debit-balance posting asset for the payment method")
    return row


def current(db, location_id, department_id, lock=False):
    query = db.query(PosOutletPolicy).filter_by(location_id=location_id, department_id=department_id)
    if lock:
        query = query.with_for_update()
    row = query.populate_existing().first()
    config = row.checkout_settings if row else None
    if config is None:
        # Preview existing mappings without saving, seeding or changing any COA.
        mappings = {r.setting_key:r.account_id for r in db.query(AccountingSetting).filter(AccountingSetting.setting_key.in_(METHOD_KEYS.values())).all()}
        config = {"discount_presets":[], "payment_methods":[{"method":method,"enabled":key in mappings,"account_id":mappings.get(key)} for method,key in METHOD_KEYS.items()]}
    config = CheckoutConfiguration(**config).model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return row, config, digest


def choices(db, user, location_id, department_id, management=False):
    from app.services.sales_transaction_service import SalesTransactionService as Sales
    Sales._require(user, "pos.view")
    if management:
        Sales._require(user, "finance.manage")
    ops.outlet(db,user,location_id,department_id)
    row,config,version = current(db,location_id,department_id)
    result = {"configuration":config,"version":version,"configured":bool(row and row.checkout_settings is not None)}
    if management:
        result["accounts"] = [{"id":a.id,"code":a.account_number,"name":a.account_name} for a in db.query(ChartOfAccount).filter(ChartOfAccount.is_active.is_(True),ChartOfAccount.is_posting.is_(True),ChartOfAccount.account_type=="ASSET",ChartOfAccount.normal_balance=="DEBIT").order_by(ChartOfAccount.account_number)]
    return result


def save(db,user,data):
    from app.services.sales_transaction_service import SalesTransactionService as Sales
    Sales._require(user,"finance.manage");Sales._require(user,"pos.view")
    ops.outlet(db,user,data.location_id,data.department_id)
    row,old,version = current(db,data.location_id,data.department_id,lock=True)
    if row is None:
        raise HTTPException(409,"Configure the outlet order mode first")
    if data.version != version:
        raise HTTPException(409,"Checkout settings changed; refresh before saving")
    for method in data.configuration.payment_methods:
        if method.enabled:
            account(db,method.account_id)
    row.checkout_settings = data.configuration.model_dump(mode="json")
    ops.audit(db,user,"UPDATE","POS_CHECKOUT_POLICY",row,{"before":old,"after":row.checkout_settings,"location_id":data.location_id,"department_id":data.department_id})
    db.commit()
    return choices(db,user,data.location_id,data.department_id,management=True)


def draft_discount(db, transaction, data, subtotal):
    if not applies(db,transaction):
        if data.discount_preset_id is not None or data.checkout_version is not None:
            raise HTTPException(422,"Outlet checkout settings apply only to Hotel F&B POS")
        return Decimal(0)
    row,config,version = current(db,transaction.location_id,transaction.department_id,lock=True)
    if (data.checkout_version is not None and data.checkout_version != version) or (row and row.checkout_settings is not None and data.checkout_version is None):
        raise HTTPException(409,"Checkout settings changed; refresh and review the order")
    previous = transaction.checkout_snapshot or {}
    selected = data.discount_preset_id if "discount_preset_id" in data.model_fields_set else (previous.get("discount_preset") or {}).get("id")
    preset = next((p for p in config["discount_presets"] if p["id"]==selected and p["enabled"]),None)
    if selected and not preset:
        raise HTTPException(422,"Choose an active discount preset in this outlet")
    amount = discount_amount(subtotal,preset)
    transaction.checkout_snapshot = {"version":version,"discount_preset":preset,"discount_amount":str(amount)}
    return amount


def discount_amount(subtotal,preset):
    subtotal = Decimal(subtotal)
    amount = Decimal(0) if not preset else (subtotal*Decimal(preset["value"])/100 if preset["kind"]=="PERCENT" else Decimal(preset["value"]))
    return min(subtotal,amount).quantize(MONEY,rounding=ROUND_HALF_UP)


def settlement(db, transaction, data, subtotal):
    row,config,version = current(db,transaction.location_id,transaction.department_id,lock=True)
    snapshot = transaction.checkout_snapshot or {}
    if (data.checkout_version is not None and data.checkout_version != version) or (row and row.checkout_settings is not None and data.checkout_version is None):
        raise HTTPException(409,"Checkout settings changed; refresh and review the order")
    selected = data.discount_preset_id if "discount_preset_id" in data.model_fields_set else (snapshot.get("discount_preset") or {}).get("id")
    preset = next((p for p in config["discount_presets"] if p["id"]==selected and p["enabled"]),None)
    if selected and not preset:
        raise HTTPException(422,"Choose an active discount preset in this outlet")
    if preset and snapshot.get("discount_preset") != preset:
        raise HTTPException(409,"Save the selected discount preset on this draft before settlement")
    amount = discount_amount(subtotal,preset)
    if data.discount_amount is not None and Decimal(data.discount_amount) != amount:
        raise HTTPException(422,"Discount must follow the selected outlet preset; free-form discount is not allowed")
    payment = next((p for p in config["payment_methods"] if p["method"]==data.payment_method and p["enabled"]),None)
    if not payment:
        raise HTTPException(422,"This payment method is not enabled for the outlet")
    payment_account = account(db,payment["account_id"])
    transaction.checkout_snapshot = {"version":version,"discount_preset":preset,"discount_amount":str(amount),"payment_method":data.payment_method,"payment_account_id":payment_account.id}
    return amount,payment_account
