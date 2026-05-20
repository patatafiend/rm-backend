from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.user import UserModel
from app.services.user import UserService
from app.schemas.user import (
    UserRead, UserUpdate, AdminUserUpdate,
    PaginatedUsers, DeviceRead, SigninHistoryRead,
    ChangePasswordRequest,
)

router = APIRouter()

@router.get("/me", response_model=UserRead)
def get_me(current_user: UserModel = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserRead)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    return UserService.update_me(db, current_user, payload)

@router.put("/me/password", status_code=status.HTTP_200_OK)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    UserService.change_password(db, current_user, payload)
    return {"message": "Password updated successfully"}

@router.get("/", response_model=PaginatedUsers, dependencies=[Depends(require_admin)])
def list_users(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    account_type: str | None = Query(None),
    is_blocked: bool | None = Query(None),
    search: str | None = Query(None),
):
    return UserService.get_all(db, page, page_size, account_type, is_blocked, search)

@router.get("/{user_id}", response_model=UserRead, dependencies=[Depends(require_admin)])
def get_user(user_id: int, db: Session = Depends(get_db)):
    return UserService.get_by_id(db, user_id)

@router.put("/{user_id}", response_model=UserRead, dependencies=[Depends(require_admin)])
def update_user(user_id: int, payload: AdminUserUpdate, db: Session = Depends(get_db)):
    return UserService.admin_update(db, user_id, payload)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
def delete_user(user_id: int, db: Session = Depends(get_db)):
    UserService.delete(db, user_id)

@router.patch("/{user_id}/block", response_model=UserRead, dependencies=[Depends(require_admin)])
def toggle_block(user_id: int, db: Session = Depends(get_db)):
    return UserService.toggle_block(db, user_id)

@router.get("/{user_id}/devices", response_model=list[DeviceRead])
def get_devices(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    # users can only see their own devices unless admin
    if current_user.id != user_id and current_user.account_type not in {"admin_account", "super_admin_account"}:
        raise HTTPException(status_code=403, detail="Forbidden")
    return UserService.get_devices(db, user_id)

@router.delete("/{user_id}/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_device(
    user_id: int,
    device_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    if current_user.id != user_id and current_user.account_type not in {"admin_account", "super_admin_account"}:
        raise HTTPException(status_code=403, detail="Forbidden")
    UserService.revoke_device(db, user_id, device_id)

# ------------------------------------------------------------------ #
#  SIGNIN HISTORY                                                       #
# ------------------------------------------------------------------ #
@router.get("/{user_id}/signin-history", response_model=PaginatedUsers)
def signin_history(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    if current_user.id != user_id and current_user.account_type not in {"admin_account", "super_admin_account"}:
        raise HTTPException(status_code=403, detail="Forbidden")
    return UserService.get_signin_history(db, user_id, page, page_size)