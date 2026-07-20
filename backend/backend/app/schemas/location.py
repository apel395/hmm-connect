from pydantic import BaseModel, Field


class LocationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=120)
    location_type: str = Field(default="OFFICE", min_length=1, max_length=30)


class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    location_type: str | None = Field(default=None, max_length=30)
    is_active: bool | None = None


class LocationResponse(BaseModel):
    id: int
    code: str
    name: str
    location_type: str
    is_active: bool

    class Config:
        from_attributes = True
