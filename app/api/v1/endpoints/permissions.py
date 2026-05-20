from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import require_admin, require_super_admin
from app.services.role import PermissionService
from app.schemas.role import (
    PermissionRead, PermissionCreate, PermissionUpdate,
    PermissionAccountTypeRead, PermissionAccountTypeCreate,
)

router = APIRouter()

@router.get("/", response_model=list[PermissionRead], dependencies=[Depends(require_admin)])
def list_permissions(
    db: Session = Depends(get_db),
    resource: str | None = Query(None),
    account_type: str | None = Query(None),
):
    return PermissionService.get_all(db, resource, account_type)

@router.post("/", response_model=PermissionRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_super_admin)])
def create_permission(payload: PermissionCreate, db: Session = Depends(get_db)):
    return PermissionService.create(db, payload)

@router.get("/{permission_id}", response_model=PermissionRead,
            dependencies=[Depends(require_admin)])
def get_permission(permission_id: int, db: Session = Depends(get_db)):
    return PermissionService.get_by_id(db, permission_id)

@router.put("/{permission_id}", response_model=PermissionRead,
            dependencies=[Depends(require_super_admin)])
def update_permission(permission_id: int, payload: PermissionUpdate, db: Session = Depends(get_db)):
    return PermissionService.update(db, permission_id, payload)

@router.delete("/{permission_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_super_admin)])
def delete_permission(permission_id: int, db: Session = Depends(get_db)):
    PermissionService.delete(db, permission_id)

@router.get("/{permission_id}/account-types", response_model=list[PermissionAccountTypeRead],
            dependencies=[Depends(require_admin)])
def get_account_types(permission_id: int, db: Session = Depends(get_db)):
    return PermissionService.get_account_types(db, permission_id)

@router.post("/{permission_id}/account-types", response_model=PermissionAccountTypeRead,
             status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_super_admin)])
def assign_account_type(
    permission_id: int,
    payload: PermissionAccountTypeCreate,
    db: Session = Depends(get_db),
):
    return PermissionService.assign_account_type(db, permission_id, payload)

@router.delete("/{permission_id}/account-types/{account_type}",
               status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_super_admin)])
def revoke_account_type(permission_id: int, account_type: str, db: Session = Depends(get_db)):
    PermissionService.revoke_account_type(db, permission_id, account_type)