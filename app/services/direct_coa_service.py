from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.accounting_setting import AccountingSetting
from app.models.chart_of_account import ChartOfAccount
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine


class DirectCoaService:
    """Resolve accounting directly from master-data mappings.

    Resolved IDs are copied to transaction rows before journal creation so later
    master changes never rewrite historical accounting.
    """

    BANK_SUBTYPES = {"BANK", "CASH", "PETTY_CASH", "CASH_AND_BANK"}
    RECEIVABLE_SUBTYPES = {"ACCOUNTS_RECEIVABLE", "RECEIVABLE", "TRADE_RECEIVABLE"}

    def __init__(self, db: Session):
        self.db = db

    def account(self, account_id: int | None, label: str) -> ChartOfAccount:
        account = self.db.get(ChartOfAccount, account_id) if account_id else None
        if not account or not account.is_active or not account.is_posting:
            raise HTTPException(409, f"{label} requires an active posting COA mapping")
        return account

    def inventory_account(self, product) -> ChartOfAccount:
        account = self.account(getattr(product, "inventory_account_id", None), f"Item {product.code} inventory")
        if account.account_type != "ASSET" or account.normal_balance != "DEBIT" or account.account_subtype in self.BANK_SUBTYPES:
            raise HTTPException(409, f"Item {product.code} inventory COA must be a debit-balance non-cash asset")
        return account

    def expense_account(self, product) -> ChartOfAccount:
        account = self.account(
            getattr(product, "purchase_account_id", None),
            f"Item {product.code} consumption/expense",
        )
        if account.account_type != "EXPENSE" or account.normal_balance != "DEBIT":
            raise HTTPException(409, f"Item {product.code} consumption/expense COA must be a debit-balance expense")
        return account

    def cogs_account(self, product) -> ChartOfAccount:
        account = self.account(getattr(product, "cogs_account_id", None), f"Item {product.code} COGS")
        if account.account_type != "EXPENSE" or account.normal_balance != "DEBIT":
            raise HTTPException(409, f"Item {product.code} COGS COA must be a debit-balance expense")
        return account

    def payable_account(self, supplier) -> ChartOfAccount:
        account = self.account(getattr(supplier, "payable_account_id", None), f"Supplier {supplier.code} payable")
        if account.account_type != "LIABILITY" or account.normal_balance != "CREDIT":
            raise HTTPException(409, f"Supplier {supplier.code} payable COA must be a credit-balance liability")
        return account

    def input_vat_account(self) -> ChartOfAccount:
        setting = (
            self.db.query(AccountingSetting)
            .filter(AccountingSetting.setting_key == "INPUT_VAT_ACCOUNT")
            .first()
        )
        account = self.account(setting.account_id if setting else None, "Input VAT")
        if account.account_type != "ASSET" or account.normal_balance != "DEBIT":
            raise HTTPException(409, "Input VAT COA must be a debit-balance asset")
        return account

    def validate_invoice_debit(self, account: ChartOfAccount, *, inventory: bool) -> None:
        subtype = str(account.account_subtype or "").upper()
        code = str(account.account_number or "").strip()
        if subtype in self.BANK_SUBTYPES:
            raise HTTPException(409, "Supplier invoice cannot debit a cash or bank account")
        if subtype in self.RECEIVABLE_SUBTYPES or code.startswith(("100-200-", "100-210-")):
            raise HTTPException(409, "Supplier invoice cannot debit an accounts receivable account")
        expected_type = "ASSET" if inventory else "EXPENSE"
        if account.account_type != expected_type or account.normal_balance != "DEBIT":
            label = "inventory asset" if inventory else "expense"
            raise HTTPException(409, f"Supplier invoice line requires a debit-balance {label} COA")

    def snapshot_invoice_line(self, invoice: SupplierInvoice, line: SupplierInvoiceLine) -> ChartOfAccount:
        inventory = bool(invoice.goods_receipt and invoice.goods_receipt.destination_type == "WAREHOUSE")
        if line.account_id:
            account = self.account(line.account_id, "Supplier invoice line")
        elif line.product:
            account = self.inventory_account(line.product) if inventory else self.expense_account(line.product)
            line.account_id = account.id
        else:
            raise HTTPException(409, "Manual supplier invoice line requires a direct COA")
        self.validate_invoice_debit(account, inventory=inventory)
        return account
