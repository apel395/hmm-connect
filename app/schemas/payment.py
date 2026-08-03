from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel,Field,model_validator
class PaymentAllocationInput(BaseModel):supplier_invoice_id:int;allocated_amount:Decimal=Field(gt=0)
class PaymentCreate(BaseModel):
    supplier_id:int;payment_date:date;payment_method:Literal["BANK_TRANSFER","CASH","CHEQUE","CREDIT_CARD","PETTY_CASH","OTHER"]
    payment_account_id:int;currency:str=Field(default="IDR",min_length=3,max_length=3);total_amount:Decimal=Field(gt=0);reference_number:str|None=None;cheque_number:str|None=None;notes:str|None=None;source_type:Literal["LIVE","HISTORICAL_IMPORT"]="LIVE";allocations:list[PaymentAllocationInput]
    @model_validator(mode="after")
    def allocation_total(self):
        if len({x.supplier_invoice_id for x in self.allocations})!=len(self.allocations):raise ValueError("Duplicate invoice allocation")
        return self
class PaymentUpdate(PaymentCreate):pass
class PaymentResponse(BaseModel):
    id:int;payment_number:str;payment_date:date;amount:Decimal;payment_method:str;status:str
    class Config:from_attributes=True
