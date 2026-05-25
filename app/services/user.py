from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user import (
    UserModel,
    UserDeviceModel,
    UserSigninModel,
    RoleModel,
    Company,
    Client,
)
from app.schemas.user import (
    UserUpdate,
    AdminUserUpdate,
    AdminUserCreate,
    ChangePasswordRequest,
)
from app.core.security import verify_password, hash_password


class UserService:

    @staticmethod
    def get_all(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        account_type: str | None = None,
        is_blocked: bool | None = None,
        search: str | None = None,
    ) -> dict:
        query = db.query(UserModel)

        if account_type:
            query = query.filter(UserModel.account_type == account_type)
        if is_blocked is not None:
            query = query.filter(UserModel.is_blocked == is_blocked)
        if search:
            like = f"%{search}%"
            query = query.filter(
                UserModel.email.ilike(like)
                | UserModel.first_name.ilike(like)
                | UserModel.last_name.ilike(like)
            )

        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()

        return {"total": total, "page": page, "page_size": page_size, "items": items}

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> UserModel:
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    @staticmethod
    def update_me(db: Session, user: UserModel, payload: UserUpdate) -> UserModel:
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(user, field, value)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def change_password(db: Session, user: UserModel, payload: ChangePasswordRequest):
        if not verify_password(payload.current_password, user.password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        user.password = hash_password(payload.new_password)
        db.commit()

    @staticmethod
    def admin_update(db: Session, user_id: int, payload: AdminUserUpdate) -> UserModel:
        user = UserService.get_by_id(db, user_id)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(user, field, value)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def admin_create(db: Session, payload: AdminUserCreate) -> UserModel:
        existing = db.query(UserModel).filter(UserModel.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        if payload.role_id is not None:
            role = db.query(RoleModel).filter(RoleModel.id == payload.role_id).first()
            if not role:
                raise HTTPException(status_code=404, detail="Role not found")

        if payload.account_type == "admin_account":
            if payload.company_id is None:
                raise HTTPException(
                    status_code=400,
                    detail="company_id is required for admin_account",
                )
        elif payload.company_id is not None:
            raise HTTPException(
                status_code=400,
                detail="company_id is only allowed for admin_account",
            )

        if payload.company_id is not None:
            company = db.query(Company).filter(Company.id == payload.company_id).first()
            if not company:
                raise HTTPException(status_code=404, detail="Company not found")

        if payload.client_id is not None:
            client = db.query(Client).filter(Client.id == payload.client_id).first()
            if not client:
                raise HTTPException(status_code=404, detail="Client not found")

        user = UserModel(
            email=payload.email,
            password=hash_password(payload.password),
            first_name=payload.first_name,
            middle_name=payload.middle_name,
            last_name=payload.last_name,
            username=payload.username,
            phone_number=payload.phone_number,
            profile_url=payload.profile_url,
            account_type=payload.account_type,
            role_id=payload.role_id,
            company_id=payload.company_id
            if payload.account_type == "admin_account"
            else None,
            client_id=payload.client_id,
            is_blocked=payload.is_blocked,
            allow_skip_mfa=payload.allow_skip_mfa,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete(db: Session, user_id: int):
        user = UserService.get_by_id(db, user_id)
        db.delete(user)
        db.commit()

    @staticmethod
    def toggle_block(db: Session, user_id: int) -> UserModel:
        user = UserService.get_by_id(db, user_id)
        user.is_blocked = not user.is_blocked
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_devices(db: Session, user_id: int) -> list[UserDeviceModel]:
        UserService.get_by_id(db, user_id)  # ensures user exists
        return db.query(UserDeviceModel).filter(UserDeviceModel.user_id == user_id).all()

    @staticmethod
    def revoke_device(db: Session, user_id: int, device_id: int):
        device = db.query(UserDeviceModel).filter(
            UserDeviceModel.id == device_id,
            UserDeviceModel.user_id == user_id,
        ).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        db.delete(device)
        db.commit()

    @staticmethod
    def get_signin_history(
        db: Session,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        UserService.get_by_id(db, user_id)
        query = (
            db.query(UserSigninModel)
            .filter(UserSigninModel.user_id == user_id)
            .order_by(UserSigninModel.created_at.desc())
        )
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return {"total": total, "page": page, "page_size": page_size, "items": items}