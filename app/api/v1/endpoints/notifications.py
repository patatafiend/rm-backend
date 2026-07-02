from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_caller
from app.db.session import get_db
from app.models.appraisal import NotificationModel
from app.schemas.external import ExternalCaller

router = APIRouter()


def _serialize_notification(notification: NotificationModel) -> dict:
    return {
        "id": notification.id,
        "recipient_type": notification.recipient_type,
        "recipient_value": notification.recipient_value,
        "milestone": notification.milestone,
        "rm_tran_no": notification.rm_tran_no,
        "message": notification.message,
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
    }


@router.get("/notifications")
def get_notifications(
    unread: bool = Query(False),
    caller = Depends(get_current_caller),
    db: Session = Depends(get_db),
):
    query = db.query(NotificationModel)

    if unread:
        query = query.filter(NotificationModel.read_at.is_(None))

    if isinstance(caller, ExternalCaller):
        if caller.allowed_bus:
            query = query.filter(
                NotificationModel.recipient_type == "BU_GROUP",
                NotificationModel.recipient_value.in_(caller.allowed_bus),
            )
        else:
            query = query.filter(False)
    elif getattr(caller, "account_type", None) == "super_admin_account":
        pass
    elif getattr(getattr(caller, "role", None), "name", None):
        query = query.filter(
            NotificationModel.recipient_type == "ROLE",
            NotificationModel.recipient_value == caller.role.name,
        )
    else:
        query = query.filter(False)

    notifications = query.order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc()).all()

    return {
        "status": "success",
        "total": len(notifications),
        "data": [_serialize_notification(notification) for notification in notifications],
    }