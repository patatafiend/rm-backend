from fastapi import APIRouter, Depends, HTTPException, Query
import httpx

from app.core.dependencies import get_current_user
from app.core.bu_permissions import BU_PERMISSION_MAP
from app.models.user import UserModel, RolePermissionModel, PermissionModel
from sqlalchemy.orm import Session
from app.db.session import get_db

router = APIRouter()
EXTERNAL_API_URL = "https://cmiitdept.com/hr/api_onboarded_minor.php"


def get_allowed_bus(user: UserModel, db: Session) -> list[str] | None:
    """
    Returns list of allowed bu_tagging values for this user.
    Returns None if user has no role (treat as no access).
    Super admins (no role restrictions) could return all BUs — 
    handle that via account_type check if needed.
    """
    if not user.role_id:
        return []

    permissions = (
        db.query(PermissionModel.resource)
        .join(RolePermissionModel, RolePermissionModel.permission_id == PermissionModel.id)
        .filter(
            RolePermissionModel.role_id == user.role_id,
            PermissionModel.action == "read",
            PermissionModel.resource.in_(BU_PERMISSION_MAP.keys()),
        )
        .all()
    )

    return [BU_PERMISSION_MAP[row.resource] for row in permissions]


@router.get("/employee-requirements")
def get_employee_requirements(
    limit: int | None = Query(None, ge=1),
    offset: int | None = Query(None, ge=0),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    if current_user.account_type == "admin_account":
        allowed_bus = None
    else:
        allowed_bus = get_allowed_bus(current_user, db)
        if allowed_bus == []:
            return []

    params: dict[str, str] = {}
    if limit is not None:
        params["limit"] = str(limit)
    if offset is not None:
        params["offset"] = str(offset)

    try:
        response = httpx.get(EXTERNAL_API_URL, params=params, timeout=20.0)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="External API request failed") from exc

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="External API returned an error")

    try:
        raw = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Invalid external API response") from exc
    
    if not isinstance(raw, dict) or "data" not in raw:
        raise HTTPException(status_code=502, detail="Unexpected external API response shape")
    
    data: list[dict] = raw["data"]

    if allowed_bus is not None:
        data = [row for row in data if row.get("bu_tagging") in allowed_bus]

    return {
        "status": "success",
        "total": len(data),
        "data": data,
    }