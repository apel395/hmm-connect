from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.accounting_setting import AccountingSetting
from app.models.chart_of_account import ChartOfAccount
from app.models.journal_entry import JournalEntry
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
            raise HTTPException(409, f"{label} requires an active direct COA mapping")
        return account

    def setting_account(self, setting_key: str, label: str) -> ChartOfAccount | None:
        setting = (
            self.db.query(AccountingSetting)
            .filter(AccountingSetting.setting_key == setting_key)
            .first()
        )
        if not setting:
            return None
        return self.account(setting.account_id, label)

    def location_account(self, location_id: int | None, role: str, label: str) -> ChartOfAccount | None:
        if not location_id:
            return None
        setting = (
            self.db.query(AccountingSetting)
            .filter(AccountingSetting.setting_key == f"LOCATION_{location_id}_{role}")
            .first()
        )
        if not setting:
            return None
        return self.account(setting.account_id, label)

    @staticmethod
    def inventory_role(product) -> str:
        text = " ".join(
            str(value or "")
            for value in (
                getattr(product, "group_code", None),
                getattr(product, "group_name", None),
                getattr(product, "subgroup_code", None),
                getattr(product, "subgroup_name", None),
                getattr(product, "name", None),
            )
        ).upper()
        if any(token in text for token in ("BEVERAGE", "MINUM", "DRINK")):
            return "INVENTORY_BEVERAGE"
        if any(token in text for token in ("FOOD", "MAKAN", "GROC", "SPICE", "VEGETABLE", "MEAT", "SEAFOOD")):
            return "INVENTORY_FOOD"
        return "INVENTORY_MATERIAL"

    def inventory_account(self, product, location_id: int | None = None) -> ChartOfAccount:
        account = self.location_account(
            location_id,
            self.inventory_role(product),
            f"Item {product.code} inventory for location {location_id}",
        )
        if account is None:
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

    def payable_account(self, supplier, location_id: int | None = None) -> ChartOfAccount:
        account = self.setting_account(
            "ACCOUNTS_PAYABLE_ACCOUNT",
            "Global Accounts Payable",
        )
        if account is None:
            account = self.location_account(
                location_id,
                "AP",
                f"Accounts Payable for location {location_id}",
            )
        if account is None:
            account = self.account(
                getattr(supplier, "payable_account_id", None),
                f"Supplier {supplier.code} payable",
            )
        if account.account_type != "LIABILITY" or account.normal_balance != "CREDIT":
            raise HTTPException(409, f"Supplier {supplier.code} payable COA must be a credit-balance liability")
        return account

    def input_vat_account(self) -> ChartOfAccount:
        account = self.setting_account("INPUT_VAT_ACCOUNT", "Input VAT")
        if account is None:
            raise HTTPException(409, "Input VAT requires an active direct COA mapping")
        if account.account_type != "ASSET" or account.normal_balance != "DEBIT":
            raise HTTPException(409, "Input VAT COA must be a debit-balance asset")
        return account

    def grni_account(self) -> ChartOfAccount:
        account = self.setting_account("GRNI_ACCOUNT", "GRNI")
        if account is None:
            raise HTTPException(409, "GRNI requires an active direct COA mapping")
        if account.account_type != "LIABILITY" or account.normal_balance != "CREDIT":
            raise HTTPException(409, "GRNI COA must be a credit-balance liability")
        return account

    def purchase_discount_account(self) -> ChartOfAccount:
        account = self.setting_account(
            "PURCHASE_DISCOUNT_ACCOUNT",
            "Purchase Discount",
        )
        if account is None:
            raise HTTPException(409, "Purchase Discount requires an active direct COA mapping")
        if (
            account.account_type not in {"INCOME", "EXPENSE"}
            or account.normal_balance != "CREDIT"
        ):
            raise HTTPException(
                409,
                "Purchase Discount COA must be a credit-balance income or contra-expense account",
            )
        return account

    def withholding_tax_payable_account(self) -> ChartOfAccount:
        account = self.setting_account(
            "WITHHOLDING_TAX_PAYABLE_ACCOUNT",
            "Withholding Tax Payable",
        )
        if account is None:
            raise HTTPException(
                409,
                "Withholding Tax Payable requires an active direct COA mapping",
            )
        if account.account_type != "LIABILITY" or account.normal_balance != "CREDIT":
            raise HTTPException(
                409,
                "Withholding Tax Payable COA must be a credit-balance liability",
            )
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

    def receipt_uses_grni(self, invoice: SupplierInvoice) -> bool:
        receipt_id = getattr(invoice, "goods_receipt_id", None)
        if not receipt_id:
            return False
        journal = (
            self.db.query(JournalEntry)
            .filter(
                JournalEntry.reference_type == "GOODS_RECEIPT",
                JournalEntry.reference_id == receipt_id,
                JournalEntry.status != "VOID",
            )
            .first()
        )
        return journal is not None

    def supplier_invoice_readiness(self, invoice: SupplierInvoice) -> dict:
        """Return every accounting prerequisite without mutating the invoice."""
        blockers: list[dict[str, str]] = []

        def check(code: str, callback) -> None:
            try:
                callback()
            except HTTPException as exc:
                blockers.append({"code": code, "message": str(exc.detail)})

        check("SUPPLIER_PAYABLE", lambda: self.payable_account(invoice.supplier, invoice.location_id))
        if Decimal(invoice.tax_amount or 0) > 0:
            check("INPUT_VAT", self.input_vat_account)
        if Decimal(getattr(invoice, "discount_amount", 0) or 0) > 0:
            check("PURCHASE_DISCOUNT", self.purchase_discount_account)
        if Decimal(getattr(invoice, "withholding_tax_amount", 0) or 0) > 0:
            check("WITHHOLDING_TAX", self.withholding_tax_payable_account)

        uses_grni = self.receipt_uses_grni(invoice)
        if uses_grni:
            check("GRNI", self.grni_account)

        inventory = bool(
            invoice.goods_receipt
            and str(invoice.goods_receipt.destination_type or "").upper() == "WAREHOUSE"
        )
        for index, line in enumerate(invoice.lines, start=1):
            if uses_grni:
                continue

            def validate_line(current=line):
                if current.account_id:
                    account = self.account(current.account_id, f"Invoice line {index}")
                elif current.product:
                    account = (
                        self.inventory_account(current.product, invoice.location_id)
                        if inventory
                        else self.expense_account(current.product)
                    )
                else:
                    raise HTTPException(409, f"Invoice line {index} requires a direct COA")
                self.validate_invoice_debit(account, inventory=inventory)

            check(f"INVOICE_LINE_{index}", validate_line)

        return {"is_ready": not blockers, "blockers": blockers}

    def snapshot_invoice_line(self, invoice: SupplierInvoice, line: SupplierInvoiceLine) -> ChartOfAccount:
        inventory = bool(invoice.goods_receipt and invoice.goods_receipt.destination_type == "WAREHOUSE")
        if line.account_id:
            account = self.account(line.account_id, "Supplier invoice line")
        elif line.product:
            account = self.inventory_account(line.product, invoice.location_id) if inventory else self.expense_account(line.product)
            line.account_id = account.id
        else:
            raise HTTPException(409, "Manual supplier invoice line requires a direct COA")
        self.validate_invoice_debit(account, inventory=inventory)
        return account
