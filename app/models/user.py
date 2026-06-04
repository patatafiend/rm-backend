from typing import Optional, List
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    Integer,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
    Column,
)
from sqlalchemy.orm import Mapped, relationship
from app.db.base import Base

class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    account_type = Column(String(80))
    username = Column(String(80))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    first_name = Column(String(100))
    middle_name = Column(String(100))
    last_name = Column(String(100))
    phone_number = Column(String(20))
    is_blocked = Column(Boolean, default=False)
    profile_url = Column(String(255))
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255), nullable=True)
    mfa_temp_secret = Column(String(255), nullable=True)
    allow_skip_mfa = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    role_id = Column(
        Integer, ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
    )
    company_id = Column(Integer, ForeignKey("company.id", ondelete="SET NULL"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    
    signins: Mapped[List["UserSigninModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    signups: Mapped[List["UserSignupModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    devices: Mapped[List["UserDeviceModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    tokens: Mapped[List["UserTokenModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    reset_tokens: Mapped[List["ResetTokenModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    role: Mapped[Optional["RoleModel"]] = relationship(back_populates="users")
    company: Mapped[Optional["Company"]] = relationship(back_populates="users")
    clients: Mapped[Optional["Client"]] = relationship(back_populates="users")
    mfa_tokens: Mapped[List["MfaTokenModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

class UserSigninModel(Base):
    __tablename__ = "user_signins"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    device_type = Column(String(50))
    os_name = Column(String(50))
    os_version = Column(String(50))
    browser_name = Column(String(50))
    browser_version = Column(String(50))
    ip_address = Column(String(45))
    success = Column(Boolean, default=True)
    message = Column(String(50))

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["UserModel"] = relationship(back_populates="signins")

class UserSignupModel(Base):
    __tablename__ = "user_signups"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    device_type = Column(String(50))
    os_name = Column(String(50))
    os_version = Column(String(50))
    browser_name = Column(String(50))
    browser_version = Column(String(50))
    ip_address = Column(String(45))
    success = Column(Boolean, default=True)
    message = Column(String(50))

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["UserModel"] = relationship(back_populates="signups")

class UserDeviceModel(Base):
    __tablename__ = "user_devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    device_type = Column(String(50))
    os_name = Column(String(50))
    os_version = Column(String(50))
    browser_name = Column(String(50))
    browser_version = Column(String(50))
    ip_address = Column(String(45))
    is_trusted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["UserModel"] = relationship(back_populates="devices")
    token: Mapped[Optional["UserTokenModel"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )

class RoleModel(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    account_type = Column(
        Enum(
            "company_account",
            "admin_account",
            "client_account",
            "super_admin_account",
            name="account_type_enum",
        ),
        nullable=False,
    )
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    company_id = Column(Integer, nullable=True)
    client_id = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "name", "client_id", "company_id", name="uq_role_name_per_tenant"
        ),
        CheckConstraint(
            "(company_id IS NOT NULL AND client_id IS NULL) "
            "OR (company_id IS NULL AND client_id IS NOT NULL)"
            "OR (company_id IS NULL AND client_id IS NULL)",
            name="ck_role_one_owner",
        ),
    )

    users: Mapped[List["UserModel"]] = relationship(back_populates="role")
    role_permissions: Mapped[List["RolePermissionModel"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )

class PermissionModel(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    resource = Column(String(100))
    action = Column(String(50))
    description = Column(String(255))

    role_permissions: Mapped[List["RolePermissionModel"]] = relationship(
        back_populates="permission", cascade="all, delete-orphan"
    )
    account_type_links: Mapped[List["PermissionAccountTypeModel"]] = relationship(
        back_populates="permission", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("resource", "action", name="uq_permission_resource_action"),
    )

class PermissionAccountTypeModel(Base):
    __tablename__ = "permission_account_types"

    id = Column(Integer, primary_key=True, index=True)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"))
    account_type = Column(
        Enum(
            "company_account",
            "admin_account",
            "client_account",
            "super_admin_account",
            name="account_type_enum",
        ),
        nullable=False,
    )

    permission: Mapped["PermissionModel"] = relationship(
        back_populates="account_type_links"
    )

    __table_args__ = (
        UniqueConstraint(
            "permission_id", "account_type", name="uq_permission_account_type"
        ),
    )

class RolePermissionModel(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"))
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"))

    role: Mapped["RoleModel"] = relationship(back_populates="role_permissions")
    permission: Mapped["PermissionModel"] = relationship(
        back_populates="role_permissions"
    )


class UserTokenModel(Base):
    __tablename__ = "user_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    device_id = Column(
        Integer, ForeignKey("user_devices.id", ondelete="CASCADE"), unique=True
    )
    token = Column(String(5000))
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["UserModel"] = relationship(back_populates="tokens")
    device: Mapped["UserDeviceModel"] = relationship(back_populates="token")


class ResetTokenModel(Base):
    __tablename__ = "reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    user_email = Column(String(255), nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    used = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["UserModel"] = relationship(back_populates="reset_tokens")

class MfaTokenModel(Base):
    __tablename__ = "mfa_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["UserModel"] = relationship(back_populates="mfa_tokens")


class Company(Base):
    __tablename__ = "company"

    id = Column(Integer, primary_key=True)
    company_photo_url = Column(String(255), nullable=True)
    company_name = Column(String(100), nullable=False)
    company_email = Column(String(100), nullable=False, unique=True)
    company_address = Column(String(100), nullable=False)
    company_phone = Column(String(100), nullable=False)
    company_tel = Column(String(100), nullable=True)
    company_description = Column(String(255), nullable=True)
    status = Column(String(100), nullable=False)
    is_blocked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    users: Mapped[List["UserModel"]] = relationship(back_populates="company")
    clients: Mapped[List["Client"]] = relationship(back_populates="company")

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    client_photo_url = Column(String(255), nullable=True)
    company_id = Column(Integer, ForeignKey("company.id"), nullable=False)
    system_type = Column(String(100), nullable=False)
    client_name = Column(String(100), nullable=False)
    client_email = Column(String(100), nullable=False, unique=True)
    client_address = Column(String(100), nullable=False)
    client_phone = Column(String(100), nullable=False)
    client_tel = Column(String(100), nullable=True)
    client_description = Column(String(255), nullable=True)
    status = Column(String(100), nullable=False)
    is_blocked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    users: Mapped[List["UserModel"]] = relationship(back_populates="clients")
    company: Mapped["Company"] = relationship(back_populates="clients")

class AuthorizedDomainModel(Base):
    __tablename__ = "authorized_domains"

    id          = Column(Integer, primary_key=True, index=True)
    domain      = Column(String(255), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
