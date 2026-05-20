from pydantic import BaseModel, EmailStr
from datetime import datetime

class CompanyBase(BaseModel):
    company_name: str
    company_email: EmailStr
    company_address: str
    company_phone: str
    company_tel: str | None = None
    company_description: str | None = None
    company_photo_url: str | None = None

class CompanyCreate(CompanyBase):
    status: str = "active"

class CompanyUpdate(BaseModel):
    company_name: str | None = None
    company_email: EmailStr | None = None
    company_address: str | None = None
    company_phone: str | None = None
    company_tel: str | None = None
    company_description: str | None = None
    company_photo_url: str | None = None
    status: str | None = None

class CompanyRead(CompanyBase):
    id: int
    status: str
    is_blocked: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class CompanySummary(BaseModel):
    id: int
    company_name: str
    company_email: str
    status: str
    is_blocked: bool

    model_config = {"from_attributes": True}

class PaginatedCompanies(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CompanySummary]

class ClientBase(BaseModel):
    client_name: str
    client_email: EmailStr
    client_address: str
    client_phone: str
    client_tel: str | None = None
    client_description: str | None = None
    client_photo_url: str | None = None
    system_type: str

class ClientCreate(ClientBase):
    company_id: int
    status: str = "active"

class ClientUpdate(BaseModel):
    client_name: str | None = None
    client_email: EmailStr | None = None
    client_address: str | None = None
    client_phone: str | None = None
    client_tel: str | None = None
    client_description: str | None = None
    client_photo_url: str | None = None
    system_type: str | None = None
    status: str | None = None

class ClientRead(ClientBase):
    id: int
    company_id: int
    status: str
    is_blocked: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class ClientSummary(BaseModel):
    id: int
    client_name: str
    client_email: str
    system_type: str
    status: str
    is_blocked: bool
    company_id: int

    model_config = {"from_attributes": True}

class PaginatedClients(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ClientSummary]