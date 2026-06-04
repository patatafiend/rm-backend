from pydantic import BaseModel, EmailStr
from typing import Literal
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    phone_number: str | None = None
    profile_url: str | None = None

class UserRead(UserBase):
    id: int
    account_type: str | None = None
    is_blocked: bool
    mfa_enabled: bool
    role_id: int | None = None
    company_id: int | None = None
    client_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class UserSummary(BaseModel):
    """Lightweight — used in lists"""
    id: int
    email: str
    first_name: str | None = None
    last_name: str | None = None
    account_type: str | None = None
    is_blocked: bool

    model_config = {"from_attributes": True}

class UserUpdate(BaseModel):
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    phone_number: str | None = None
    profile_url: str | None = None

class AdminUserUpdate(UserUpdate):
    """Admin can also update role, account_type"""
    role_id: int | None = None
    account_type: str | None = None

class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    phone_number: str | None = None
    profile_url: str | None = None
    account_type: Literal[
        "admin_account",
        "user_account",
        "super_admin_account",
        "audit_account",
    ]
    role_id: int | None = None
    company_id: int | None = None
    client_id: int | None = None
    is_blocked: bool = False
    allow_skip_mfa: bool = False

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class DeviceRead(BaseModel):
    id: int
    device_type: str | None = None
    os_name: str | None = None
    os_version: str | None = None
    browser_name: str | None = None
    browser_version: str | None = None
    ip_address: str | None = None
    is_trusted: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class SigninHistoryRead(BaseModel):
    id: int
    device_type: str | None = None
    os_name: str | None = None
    browser_name: str | None = None
    ip_address: str | None = None
    success: bool
    message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
class PaginatedUsers(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[UserSummary]