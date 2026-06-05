from pydantic import BaseModel, EmailStr
from app.schemas.user import UserResponse

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    username: str | None = None
    phone_number: str | None = None
    account_type: str

class RegisterResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    account_type: str

    model_config = {"from_attributes": True}

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_token: str | None = None
    user: UserResponse | None = None
class RefreshRequest(BaseModel):
    refresh_token: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class MfaSetupResponse(BaseModel):
    secret: str
    qr_uri: str

class MfaVerifySetupRequest(BaseModel):
    code: str

class MfaVerifyRequest(BaseModel):
    mfa_token: str
    code: str

class MfaDisableRequest(BaseModel):
    code: str