from pydantic import BaseModel


class ItemGroupCreate(BaseModel):
    code: str
    name: str


class ItemGroupResponse(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool

    class Config:
        from_attributes = True


class ItemSubgroupCreate(BaseModel):
    code: str
    name: str
    group_id: int


class ItemSubgroupResponse(BaseModel):
    id: int
    code: str
    name: str
    group_id: int
    is_active: bool

    class Config:
        from_attributes = True
