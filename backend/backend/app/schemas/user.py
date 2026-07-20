from pydantic import BaseModel, EmailStr, Field


class UserLogin(BaseModel):
    username: str
    password: str


class RoleResponse(BaseModel):
    id: int
    name: str
    description: str | None

    class Config:
        from_attributes = True


class DepartmentResponse(BaseModel):
    id: int
    code: str
    name: str

    class Config:
        from_attributes = True


class LocationResponse(BaseModel):
    id: int
    code: str
    name: str
    location_type: str

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    full_name: str
    is_active: bool
    department_id: int | None
    department: DepartmentResponse | None = None
    location_id: int | None
    location: LocationResponse | None = None
    roles: list[RoleResponse] = []

    class Config:
        from_attributes = True


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=8, max_length=128)
    department_id: int | None = None
    location_id: int | None = None
    role_id: int | None = None


class AssignRoleRequest(BaseModel):
    role_id: int


class AssignDepartmentRequest(BaseModel):
    department_id: int | None


class AssignLocationRequest(BaseModel):
    location_id: int | None
