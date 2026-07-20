from pydantic import BaseModel


class ChartOfAccountResponse(BaseModel):
    id: int
    account_number: str
    account_name: str
    account_type: str
    is_active: bool

    class Config:
        from_attributes = True
