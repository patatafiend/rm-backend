from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import (
    RoleModel, PermissionModel,
    RolePermissionModel, PermissionAccountTypeModel,
)
from app.schemas.role import (
    RoleCreate, RoleUpdate,
    PermissionCreate, PermissionUpdate,
    PermissionAccountTypeCreate,
    RolePermissionAssign,
)


class RoleService:

    @staticmethod
    def get_all(
        db: Session,
        company_id: int | None = None,
        client_id: int | None = None,
        account_type: str | None = None,
    ) -> list[RoleModel]:
        query = db.query(RoleModel)

        if company_id is not None:
            query = query.filter(RoleModel.company_id == company_id)
        if client_id is not None:
            query = query.filter(RoleModel.client_id == client_id)
        if account_type:
            query = query.filter(RoleModel.account_type == account_type)

        return query.all()

    @staticmethod
    def get_by_id(db: Session, role_id: int) -> RoleModel:
        role = db.query(RoleModel).filter(RoleModel.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        return role

    @staticmethod
    def create(db: Session, payload: RoleCreate) -> RoleModel:
        if payload.company_id and payload.client_id:
            raise HTTPException(
                status_code=400,
                detail="Role can belong to either a company or a client, not both",
            )

        existing = db.query(RoleModel).filter(
            RoleModel.name == payload.name,
            RoleModel.company_id == payload.company_id,
            RoleModel.client_id == payload.client_id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Role with this name already exists for this tenant",
            )

        role = RoleModel(**payload.model_dump())
        db.add(role)
        db.commit()
        db.refresh(role)
        return role

    @staticmethod
    def update(db: Session, role_id: int, payload: RoleUpdate) -> RoleModel:
        role = RoleService.get_by_id(db, role_id)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(role, field, value)
        db.commit()
        db.refresh(role)
        return role

    @staticmethod
    def delete(db: Session, role_id: int):
        role = RoleService.get_by_id(db, role_id)
        db.delete(role)
        db.commit()

    @staticmethod
    def get_permissions(db: Session, role_id: int) -> list[RolePermissionModel]:
        RoleService.get_by_id(db, role_id)
        return (
            db.query(RolePermissionModel)
            .filter(RolePermissionModel.role_id == role_id)
            .all()
        )

    @staticmethod
    def assign_permission(
        db: Session, role_id: int, payload: RolePermissionAssign
    ) -> RolePermissionModel:
        RoleService.get_by_id(db, role_id)

        permission = db.query(PermissionModel).filter(
            PermissionModel.id == payload.permission_id
        ).first()
        if not permission:
            raise HTTPException(status_code=404, detail="Permission not found")

        existing = db.query(RolePermissionModel).filter(
            RolePermissionModel.role_id == role_id,
            RolePermissionModel.permission_id == payload.permission_id,
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Permission already assigned to role")

        rp = RolePermissionModel(role_id=role_id, permission_id=payload.permission_id)
        db.add(rp)
        db.commit()
        db.refresh(rp)
        return rp

    @staticmethod
    def revoke_permission(db: Session, role_id: int, permission_id: int):
        rp = db.query(RolePermissionModel).filter(
            RolePermissionModel.role_id == role_id,
            RolePermissionModel.permission_id == permission_id,
        ).first()
        if not rp:
            raise HTTPException(status_code=404, detail="Permission not assigned to this role")
        db.delete(rp)
        db.commit()


class PermissionService:

    @staticmethod
    def get_all(
        db: Session,
        resource: str | None = None,
        account_type: str | None = None,
    ) -> list[PermissionModel]:
        query = db.query(PermissionModel)

        if resource:
            query = query.filter(PermissionModel.resource.ilike(f"%{resource}%"))

        if account_type:
            query = query.join(PermissionModel.account_type_links).filter(
                PermissionAccountTypeModel.account_type == account_type
            )

        return query.all()

    @staticmethod
    def get_by_id(db: Session, permission_id: int) -> PermissionModel:
        perm = db.query(PermissionModel).filter(PermissionModel.id == permission_id).first()
        if not perm:
            raise HTTPException(status_code=404, detail="Permission not found")
        return perm

    @staticmethod
    def create(db: Session, payload: PermissionCreate) -> PermissionModel:
        existing = db.query(PermissionModel).filter(
            PermissionModel.resource == payload.resource,
            PermissionModel.action == payload.action,
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Permission '{payload.resource}:{payload.action}' already exists",
            )

        perm = PermissionModel(**payload.model_dump())
        db.add(perm)
        db.commit()
        db.refresh(perm)
        return perm

    @staticmethod
    def update(db: Session, permission_id: int, payload: PermissionUpdate) -> PermissionModel:
        perm = PermissionService.get_by_id(db, permission_id)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(perm, field, value)
        db.commit()
        db.refresh(perm)
        return perm

    @staticmethod
    def delete(db: Session, permission_id: int):
        perm = PermissionService.get_by_id(db, permission_id)
        db.delete(perm)
        db.commit()

    @staticmethod
    def get_account_types(db: Session, permission_id: int) -> list[PermissionAccountTypeModel]:
        PermissionService.get_by_id(db, permission_id)
        return db.query(PermissionAccountTypeModel).filter(
            PermissionAccountTypeModel.permission_id == permission_id
        ).all()

    @staticmethod
    def assign_account_type(
        db: Session, permission_id: int, payload: PermissionAccountTypeCreate
    ) -> PermissionAccountTypeModel:
        PermissionService.get_by_id(db, permission_id)

        existing = db.query(PermissionAccountTypeModel).filter(
            PermissionAccountTypeModel.permission_id == permission_id,
            PermissionAccountTypeModel.account_type == payload.account_type,
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Account type already linked")

        link = PermissionAccountTypeModel(
            permission_id=permission_id,
            account_type=payload.account_type,
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        return link

    @staticmethod
    def revoke_account_type(db: Session, permission_id: int, account_type: str):
        link = db.query(PermissionAccountTypeModel).filter(
            PermissionAccountTypeModel.permission_id == permission_id,
            PermissionAccountTypeModel.account_type == account_type,
        ).first()
        if not link:
            raise HTTPException(status_code=404, detail="Account type not linked to this permission")
        db.delete(link)
        db.commit()