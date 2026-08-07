from fastapi import APIRouter, Depends, Request, status, HTTPException, Query
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse
from app.core.config import settings
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
from urllib.parse import urlparse
from app.core.bu_permissions import (
    BU_GROUP_MAP,
    APPRAISALS_BU_GROUP_MAP,
    APPRAISALS_CATEGORY_MAP,
    APPRAISALS_CATEGORY_ALIASES,
)
from app.core.security import create_external_access_token
from app.models.user import AuthorizedDomainModel

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

@router.get("/authorize")
def authorize_external(
    employee_id: str = Query(...),
    bu_group: str = Query(...),
    system: str = Query("rm"),  # "rm" | "analytics" | "appraisals"
    category: str | None = Query(None),  # "staff" | "non_staff" — appraisals only, optional
    db: Session = Depends(get_db),
):
    VALID_SYSTEMS = {"rm", "analytics", "appraisals"}
    if system not in VALID_SYSTEMS:
        raise HTTPException(status_code=400, detail=f"Unknown system '{system}'. Valid: {list(VALID_SYSTEMS)}")

    # appraisals (PAM) keys bu_tagging off the newer, bundled-only feed
    # data (Security/MWFL) — rm and analytics still key off the older,
    # granular bu_tagging values, so they keep the original map.
    group_map = APPRAISALS_BU_GROUP_MAP if system == "appraisals" else BU_GROUP_MAP

    groups = [g.strip() for g in bu_group.split(",")]
    allowed_bus = []
    invalid_groups = []

    for group in groups:
        key = group.strip().lower()
        if key not in group_map:
            invalid_groups.append(group)
        else:
            allowed_bus.extend(group_map[key])

    if invalid_groups:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown bu_group(s): {invalid_groups}. Valid: {list(group_map.keys())}"
        )

    allowed_bus = list(set(allowed_bus))

    allowed_categories: list[str] | None = None
    if category is not None:
        if system != "appraisals":
            raise HTTPException(
                status_code=400,
                detail="category is only supported for system=appraisals",
            )
        cat_keys = [c.strip().lower().replace("-", "_") for c in category.split(",")]
        allowed_categories = []
        invalid_categories = []
        for key in cat_keys:
            bucket = APPRAISALS_CATEGORY_ALIASES.get(key, key)
            if bucket not in APPRAISALS_CATEGORY_MAP:
                invalid_categories.append(key)
            else:
                allowed_categories.extend(APPRAISALS_CATEGORY_MAP[bucket])
        if invalid_categories:
            valid_values = list(APPRAISALS_CATEGORY_MAP.keys()) + list(APPRAISALS_CATEGORY_ALIASES.keys())
            raise HTTPException(
                status_code=400,
                detail=f"Unknown category value(s): {invalid_categories}. Valid: {valid_values}"
            )
        allowed_categories = list(set(allowed_categories))

    access_token = create_external_access_token(
        employee_id=employee_id,
        bu_group=bu_group,
        allowed_bus=allowed_bus,
        allowed_categories=allowed_categories,
    )

    # Route to the right frontend path based on system
    route_map = {
    "rm": "/external?redirect=/dashboard",
    "analytics": "/external?redirect=/analytics",
    "appraisals": "/external?redirect=/appraisals",
    }

    redirect_url = f"{settings.FRONTEND_URL}{route_map[system]}&token={access_token}"
    return RedirectResponse(url=redirect_url, status_code=302)


