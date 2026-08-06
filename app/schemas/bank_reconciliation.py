from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field

class ReconciliationCreate(BaseModel):
    account_id:int;statement_start_date:date;statement_end_date:date
    statement_opening_balance:Decimal;statement_closing_balance:Decimal;notes:str|None=None
class ReconciliationUpdate(BaseModel):
    statement_start_date:date|None=None;statement_end_date:date|None=None
    statement_opening_balance:Decimal|None=None;statement_closing_balance:Decimal|None=None;notes:str|None=None
class MatchAllocation(BaseModel):
    statement_line_id:int;journal_line_id:int;matched_amount:Decimal=Field(gt=0);match_type:str="MANUAL";confidence_score:Decimal|None=None
class MatchCreate(BaseModel):allocations:list[MatchAllocation]
class AutoMatchRequest(BaseModel):date_tolerance_days:int=Field(3,ge=0,le=30);confirm_suggested:bool=False
class AdjustmentCreate(BaseModel):
    statement_line_id:int;adjustment_type:str;posting_date:date;description:str
    debit_account_id:int;credit_account_id:int;amount:Decimal=Field(gt=0);notes:str|None=None
