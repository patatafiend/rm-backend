from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import decode_token
from app.models.user import UserModel
from app.schemas.external import ExternalCaller

bearer = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> UserModel:
    token = credentials.credentials
    payload = decode_token(token, token_type="access")

    user = db.query(UserModel).filter(UserModel.id == int(payload["sub"])).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.is_blocked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is blocked")

    return user

ADMIN_TYPES = {1, "super_admin_account"}

def require_admin(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    if current_user.role_id not in ADMIN_TYPES:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

def require_super_admin(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    if current_user.account_type != "super_admin_account":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return current_user

def get_current_caller(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> UserModel | ExternalCaller:
    token = credentials.credentials
    
    # Decode without type check first so we can branch on type
    payload = decode_token(token)  # ← no token_type argument

    if payload.get("type") == "external":
        return ExternalCaller(
            employee_id=payload["sub"],
            bu_group=payload.get("bu_group", ""),
            allowed_bus=payload.get("allowed_bus", []),
        )

    # For normal users, enforce access type
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = int(payload["sub"])
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.is_blocked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is blocked")

    return user