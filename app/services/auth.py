import secrets
import pyotp
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.utils.datetime import as_utc

from app.core.config import settings
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.models.user import (
    UserModel, UserSigninModel, UserSignupModel,
    UserDeviceModel, UserTokenModel, ResetTokenModel,
    MfaTokenModel,
)
from app.schemas.auth import (
    RegisterRequest, LoginRequest,
    ResetPasswordRequest, MfaVerifySetupRequest,
    MfaVerifyRequest, MfaDisableRequest,
)
from app.schemas.device import DeviceInfo
from app.schemas.user import UserResponse


class AuthService:

    @staticmethod
    def register(db: Session, payload: RegisterRequest, device: DeviceInfo) -> UserModel:
        existing = db.query(UserModel).filter(UserModel.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        user = UserModel(
            email=payload.email,
            password=hash_password(payload.password),
            first_name=payload.first_name,
            last_name=payload.last_name,
            username=payload.username,
            phone_number=payload.phone_number,
            account_type=payload.account_type,
        )
        db.add(user)
        db.flush()  # get user.id without committing

        db.add(UserSignupModel(user_id=user.id, **device.model_dump(), success=True))
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def login(db: Session, payload: LoginRequest, device: DeviceInfo) -> dict:
        user = db.query(UserModel).filter(UserModel.email == payload.email).first()

        success = bool(user and verify_password(payload.password, user.password))

        if user:
            db.add(UserSigninModel(
                user_id=user.id,
                **device.model_dump(),
                success=success,
                message="Login successful" if success else "Invalid password",
            ))

        if not user:
            db.commit()
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not success:
            db.commit()
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if user.is_blocked:
            db.commit()
            raise HTTPException(status_code=403, detail="Account is blocked")

        db.commit()

        if user.mfa_enabled:
            mfa_token = AuthService._create_mfa_token(db, user.id)
            return {"mfa_required": True, "mfa_token": mfa_token}

        access  = create_access_token(user.id)
        refresh = create_refresh_token(user.id)
        AuthService._upsert_device_token(db, user.id, device, refresh)

        return {"access_token": access, "refresh_token": refresh, "mfa_required": False, "user": UserResponse.model_validate(user),}

    @staticmethod
    def refresh(db: Session, refresh_token: str) -> dict:
        payload = decode_token(refresh_token, token_type="refresh")

        token_row = db.query(UserTokenModel).filter(
            UserTokenModel.token == refresh_token
        ).first()
        if not token_row or as_utc(token_row.expires_at) < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Refresh token expired or revoked")

        user_id = int(payload["sub"])
        new_access = create_access_token(user_id)
        new_refresh = create_refresh_token(user_id)
        
        # Rotate refresh token: delete old, insert new
        db.delete(token_row)
        db.add(UserTokenModel(
            user_id=user_id,
            token=new_refresh,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ))
        db.commit()
        
        return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}

    @staticmethod
    def logout(db: Session, user: UserModel, refresh_token: str):
        token_row = db.query(UserTokenModel).filter(
            UserTokenModel.user_id == user.id,
            UserTokenModel.token == refresh_token,
        ).first()
        if token_row:
            db.delete(token_row)
            db.commit()

    @staticmethod
    def forgot_password(db: Session, email: str):
        user = db.query(UserModel).filter(UserModel.email == email).first()
        if not user:
            return  # silently return — don't leak user existence

        token = secrets.token_urlsafe(32)
        db.add(ResetTokenModel(
            user_id=user.id,
            user_email=email,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        db.commit()

        # TODO: send token via email service
        # email_service.send_reset_email(email, token)
        return token  # remove in production; only for dev/testing

    @staticmethod
    def reset_password(db: Session, payload: ResetPasswordRequest):
        reset = db.query(ResetTokenModel).filter(
            ResetTokenModel.token == payload.token,
            ResetTokenModel.used == False,
        ).first()

        if not reset or as_utc(reset.expires_at) < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        user = db.query(UserModel).filter(UserModel.id == reset.user_id).first()
        user.password = hash_password(payload.new_password)
        reset.used = True
        db.commit()

    @staticmethod
    def mfa_setup(db: Session, user: UserModel) -> dict:
        secret = pyotp.random_base32()
        user.mfa_temp_secret = secret
        db.commit()

        uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email, issuer_name="RequirementsMonitoringApp"
        )
        return {"secret": secret, "qr_uri": uri}

    @staticmethod
    def mfa_verify_setup(db: Session, user: UserModel, payload: MfaVerifySetupRequest):
        if not user.mfa_temp_secret:
            raise HTTPException(status_code=400, detail="MFA setup not initiated")

        totp = pyotp.TOTP(user.mfa_temp_secret)
        if not totp.verify(payload.code):
            raise HTTPException(status_code=400, detail="Invalid TOTP code")

        user.mfa_secret = user.mfa_temp_secret
        user.mfa_temp_secret = None
        user.mfa_enabled = True
        db.commit()

    @staticmethod
    def mfa_verify(db: Session, payload: MfaVerifyRequest) -> dict:
        mfa_row = db.query(MfaTokenModel).filter(
            MfaTokenModel.token == payload.mfa_token,
        ).first()

        if not mfa_row or as_utc(mfa_row.expires_at) < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="MFA token expired")

        user = db.query(UserModel).filter(UserModel.id == mfa_row.user_id).first()
        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(payload.code):
            raise HTTPException(status_code=400, detail="Invalid TOTP code")

        db.delete(mfa_row)
        db.commit()

        access  = create_access_token(user.id)
        refresh = create_refresh_token(user.id)
        return {"access_token": access, "refresh_token": refresh}

    @staticmethod
    def mfa_disable(db: Session, user: UserModel, payload: MfaDisableRequest):
        if not user.mfa_enabled:
            raise HTTPException(status_code=400, detail="MFA is not enabled")

        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(payload.code):
            raise HTTPException(status_code=400, detail="Invalid TOTP code")

        user.mfa_enabled = False
        user.mfa_secret = None
        user.allow_skip_mfa = False
        db.commit()

    @staticmethod
    def _create_mfa_token(db: Session, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        db.add(MfaTokenModel(
            user_id=user_id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        ))
        db.commit()
        return token

    @staticmethod
    def _upsert_device_token(db: Session, user_id: int, device: DeviceInfo, refresh_token: str):
        device_row = db.query(UserDeviceModel).filter(
            UserDeviceModel.user_id == user_id,
            UserDeviceModel.ip_address == device.ip_address,
        ).first()

        if not device_row:
            device_row = UserDeviceModel(user_id=user_id, **device.model_dump())
            db.add(device_row)
            db.flush()

        existing_token = db.query(UserTokenModel).filter(
            UserTokenModel.device_id == device_row.id
        ).first()

        expires = datetime.now(timezone.utc) + timedelta(days=7)
        if existing_token:
            existing_token.token = refresh_token
            existing_token.expires_at = expires
        else:
            db.add(UserTokenModel(
                user_id=user_id,
                device_id=device_row.id,
                token=refresh_token,
                expires_at=expires,
            ))
        db.commit()