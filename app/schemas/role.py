from pydantic import BaseModel
from datetime import datetime

class PermissionRead(BaseModel):
    id: int
    resource: str
    action: str
    description: str | None = None

    model_config = {"from_attributes": True}

class PermissionCreate(BaseModel):
    resource: str
    action: str
    description: str | None = None

class PermissionUpdate(BaseModel):
    resource: str | None = None
    action: str | None = None
    description: str | None = None

class PermissionAccountTypeRead(BaseModel):
    id: int
    permission_id: int
    account_type: str

    model_config = {"from_attributes": True}

class PermissionAccountTypeCreate(BaseModel):
    account_type: str  # company_account | admin_account | client_account | super_admin_account

class RoleRead(BaseModel):
    id: int
    name: str
    description: str | None = None
    account_type: str
    company_id: int | None = None
    client_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class RoleWithPermissions(RoleRead):
    """Full role with its permissions expanded"""
    permissions: list[PermissionRead] = []

    model_config = {"from_attributes": True}

class RoleCreate(BaseModel):
    name: str
    description: str | None = None
    account_type: str
    company_id: int | None = None
    client_id: int | None = None

class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

class RolePermissionAssign(BaseModel):
    permission_id: int

class RolePermissionRead(BaseModel):
    id: int
    role_id: int
    permission_id: int
    permission: PermissionRead

    model_config = {"from_attributes": True}