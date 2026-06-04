from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import UserModel
from app.services.auth import AuthService
from app.schemas.auth import (
    RegisterRequest, RegisterResponse,
    LoginRequest, LoginResponse,
    RefreshRequest,
    ForgotPasswordRequest, ResetPasswordRequest,
    MfaSetupResponse, MfaVerifySetupRequest,
    MfaVerifyRequest, MfaDisableRequest,
)
from app.schemas.device import DeviceInfo

router = APIRouter()

def extract_device(request: Request) -> DeviceInfo:
    """Pull basic device info from request headers."""
    ua = request.headers.get("user-agent", "")
    return DeviceInfo(
        ip_address=request.client.host,
        device_type="mobile" if "Mobile" in ua else "desktop",
        browser_name=ua.split("/")[0] if ua else None,
    )

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    device = extract_device(request)
    user = AuthService.register(db, payload, device)
    return user

@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    device = extract_device(request)
    result = AuthService.login(db, payload, device)
    return result

@router.post("/refresh-token")
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    return AuthService.refresh(db, payload.refresh_token)

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    AuthService.logout(db, current_user, payload.refresh_token)

@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    AuthService.forgot_password(db, payload.email)
    return {"message": "If that email exists, a reset link was sent"}

@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    AuthService.reset_password(db, payload)
    return {"message": "Password reset successful"}

@router.post("/mfa/setup", response_model=MfaSetupResponse)
def mfa_setup(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    return AuthService.mfa_setup(db, current_user)

@router.post("/mfa/verify-setup", status_code=status.HTTP_200_OK)
def mfa_verify_setup(
    payload: MfaVerifySetupRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    AuthService.mfa_verify_setup(db, current_user, payload)
    return {"message": "MFA enabled successfully"}

@router.post("/mfa/verify", response_model=LoginResponse)
def mfa_verify(payload: MfaVerifyRequest, db: Session = Depends(get_db)):
    return AuthService.mfa_verify(db, payload)

@router.post("/mfa/disable", status_code=status.HTTP_200_OK)
def mfa_disable(
    payload: MfaDisableRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    AuthService.mfa_disable(db, current_user, payload)
    return {"message": "MFA disabled"}