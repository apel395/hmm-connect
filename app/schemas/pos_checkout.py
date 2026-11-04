from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from app.schemas.pos_operations import OutletContext


class DiscountPreset(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["PERCENT", "FIXED"]
    value: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    enabled: bool = True

    @model_validator(mode="after")
    def valid_value(self):
        if not self.name.strip() or (self.kind == "PERCENT" and self.value > 100):
            raise ValueError("Use a preset name and percentage no greater than 100")
        return self


class PaymentMethodSetting(BaseModel):
    method: Literal["CASH", "CARD", "BANK_TRANSFER"]
    enabled: bool
    account_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def account_required(self):
        if self.enabled and self.account_id is None:
            raise ValueError("An enabled payment method requires an account")
        return self


class CheckoutConfiguration(BaseModel):
    discount_presets: list[DiscountPreset] = Field(default_factory=list, max_length=100)
    payment_methods: list[PaymentMethodSetting] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def unique_options(self):
        if len({p.id for p in self.discount_presets}) != len(self.discount_presets):
            raise ValueError("Discount preset IDs must be unique")
        if {p.method for p in self.payment_methods} != {"CASH", "CARD", "BANK_TRANSFER"}:
            raise ValueError("Configure Cash, Card and Bank Transfer once each")
        return self


class CheckoutConfigurationSave(OutletContext):
    version: str = Field(min_length=1, max_length=64)
    configuration: CheckoutConfiguration
