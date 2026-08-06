from datetime import datetime

from pydantic import BaseModel, Field


class BusinessUnitCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    is_active: bool = True


class BusinessUnitUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=30)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    is_active: bool | None = None


class BusinessUnitResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None


class DepartmentCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    business_unit_id: int | None = None
    is_active: bool = True


class DepartmentUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=30)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    business_unit_id: int | None = None
    is_active: bool | None = None


class DepartmentResponse(BaseModel):
    id: int
    code: str
    name: str
    business_unit_id: int | None
    business_unit_name: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LocationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=120)
    business_unit_id: int
    location_type: str = Field(default="OFFICE", min_length=1, max_length=30)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    province: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    is_active: bool = True


class LocationUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=30)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    business_unit_id: int | None = None
    location_type: str | None = Field(default=None, min_length=1, max_length=30)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    province: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class LocationResponse(BaseModel):
    id: int
    code: str
    name: str
    business_unit_id: int
    business_unit_name: str
    location_type: str
    address: str | None
    city: str | None
    province: str | None
    postal_code: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
