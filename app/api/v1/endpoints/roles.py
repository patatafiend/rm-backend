from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import require_admin, require_super_admin
from app.services.role import RoleService
from app.schemas.role import (
    RoleRead, RoleWithPermissions,
    RoleCreate, RoleUpdate,
    RolePermissionAssign, RolePermissionRead,
)

router = APIRouter()

@router.get("/", response_model=list[RoleRead], dependencies=[Depends(require_admin)])
def list_roles(
    db: Session = Depends(get_db),
    company_id: int | None = Query(None),
    client_id: int | None = Query(None),
    account_type: str | None = Query(None),
):
    return RoleService.get_all(db, company_id, client_id, account_type)

@router.post("/", response_model=RoleRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
def create_role(payload: RoleCreate, db: Session = Depends(get_db)):
    return RoleService.create(db, payload)

@router.get("/{role_id}", response_model=RoleWithPermissions,
            dependencies=[Depends(require_admin)])
def get_role(role_id: int, db: Session = Depends(get_db)):
    return RoleService.get_by_id(db, role_id)

@router.put("/{role_id}", response_model=RoleRead, dependencies=[Depends(require_admin)])
def update_role(role_id: int, payload: RoleUpdate, db: Session = Depends(get_db)):
    return RoleService.update(db, role_id, payload)

@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_super_admin)])
def delete_role(role_id: int, db: Session = Depends(get_db)):
    RoleService.delete(db, role_id)

@router.get("/{role_id}/permissions", response_model=list[RolePermissionRead],
            dependencies=[Depends(require_admin)])
def get_role_permissions(role_id: int, db: Session = Depends(get_db)):
    return RoleService.get_permissions(db, role_id)

@router.post("/{role_id}/permissions", response_model=RolePermissionRead,
             status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
def assign_permission(role_id: int, payload: RolePermissionAssign, db: Session = Depends(get_db)):
    return RoleService.assign_permission(db, role_id, payload)

@router.delete("/{role_id}/permissions/{permission_id}",
               status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
def revoke_permission(role_id: int, permission_id: int, db: Session = Depends(get_db)):
    RoleService.revoke_permission(db, role_id, permission_id)