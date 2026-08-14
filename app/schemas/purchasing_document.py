from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PurchasingDocumentBase(BaseModel):
    document_type: str = Field(min_length=1, max_length=50)
    document_number: str = Field(min_length=1, max_length=100)
    document_date: date
    status: str = Field(min_length=1, max_length=50)
    source_type: str = Field(min_length=1, max_length=30)
    supplier_id: int | None = None
    department_id: int | None = None
    location_id: int | None = None
    responsible_user_id: int | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    subtotal: Decimal | None = Field(default=None, ge=0)
    tax_amount: Decimal | None = Field(default=None, ge=0)
    total_amount: Decimal | None = Field(default=None, ge=0)
    cashflow_stage: str | None = Field(default=None, max_length=30)
    expected_payment_date: date | None = None
    external_reference: str | None = Field(default=None, max_length=150)
    notes: str | None = None

    @field_validator(
        "document_type",
        "document_number",
        "status",
        "source_type",
        "cashflow_stage",
        mode="before",
    )
    @classmethod
    def normalize_codes(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None
        return value

    @field_validator("external_reference", "notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @model_validator(mode="after")
    def calculate_total(self):
        if (
            self.total_amount is None
            and self.subtotal is not None
            and self.tax_amount is not None
        ):
            self.total_amount = self.subtotal + self.tax_amount
        return self


class PurchasingDocumentCreate(PurchasingDocumentBase):
    pass


class PurchasingDocumentUpdate(BaseModel):
    document_type: str | None = Field(default=None, min_length=1, max_length=50)
    document_number: str | None = Field(default=None, min_length=1, max_length=100)
    document_date: date | None = None
    status: str | None = Field(default=None, min_length=1, max_length=50)
    source_type: str | None = Field(default=None, min_length=1, max_length=30)
    supplier_id: int | None = None
    department_id: int | None = None
    location_id: int | None = None
    responsible_user_id: int | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    subtotal: Decimal | None = Field(default=None, ge=0)
    tax_amount: Decimal | None = Field(default=None, ge=0)
    total_amount: Decimal | None = Field(default=None, ge=0)
    cashflow_stage: str | None = Field(default=None, min_length=1, max_length=30)
    expected_payment_date: date | None = None
    external_reference: str | None = Field(default=None, max_length=150)
    notes: str | None = None

    @field_validator(
        "document_type",
        "document_number",
        "status",
        "source_type",
        "cashflow_stage",
        mode="before",
    )
    @classmethod
    def normalize_codes(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().upper()
            return normalized or None
        return value

    @field_validator("external_reference", "notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value


class PurchasingDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_type: str
    document_number: str
    document_date: date
    status: str
    source_type: str
    supplier_id: int | None
    department_id: int | None
    location_id: int | None
    responsible_user_id: int | None
    currency: str | None
    subtotal: Decimal | None
    tax_amount: Decimal | None
    total_amount: Decimal | None
    cashflow_stage: str
    expected_payment_date: date | None
    external_reference: str | None
    notes: str | None
    is_active: bool
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    supplier_name: str | None = None
    department_name: str | None = None
    location_name: str | None = None
    responsible_user_name: str | None = None
    attachment_count: int = 0
    related_document_count: int = 0


class PurchasingDocumentListItem(PurchasingDocumentRead):
    pass


class PurchasingDocumentListResponse(BaseModel):
    items: list[PurchasingDocumentListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class PurchasingDocumentSummary(BaseModel):
    planned_amount: Decimal
    committed_amount: Decimal
    expected_this_month: Decimal
    missing_supplier_count: int
    missing_amount_count: int
    missing_attachment_count: int
    purchase_requisition_count: int
    purchase_order_count: int
