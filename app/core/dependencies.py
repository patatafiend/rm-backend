from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import decode_token
from app.models.user import UserModel

bearer = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> UserModel:
    token = credentials.credentials
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(UserModel).filter(UserModel.id == int(payload["sub"])).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.is_blocked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is blocked")

    return user

ADMIN_TYPES = {"admin", "super_admin_account"}

def require_admin(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    if current_user.role not in ADMIN_TYPES:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

def require_super_admin(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    if current_user.account_type != "super_admin_account":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return current_user