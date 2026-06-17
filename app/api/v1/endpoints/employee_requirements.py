from fastapi import APIRouter, Depends, HTTPException, Query
import httpx

from app.core.dependencies import get_current_user
from app.core.bu_permissions import BU_PERMISSION_MAP
from app.core.requirements import UNIVERSAL_REQUIRED_REQS, COMPANY_SPECIFIC_REQS
from app.models.user import UserModel, RolePermissionModel, PermissionModel
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.external import ExternalCaller
from app.core.dependencies import get_current_caller

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


def exclude_short_term(data: list[dict]) -> list[dict]:
    """
    Exclude employees with emp_status = 'SHORT TERM' (case-insensitive).
    """
    return [
        employee
        for employee in data
        if employee.get("emp_status", "").strip().upper() != "SHORT TERM"
    ]


def deduplicate_employees(data: list[dict]) -> list[dict]:
    """
    Deduplicate employees by (rm_tran_no, erms_id).
    When duplicates are found, merge minor_reqs into a single semicolon-separated string,
    deduplicating the requirement values within that merged string.
    """
    seen = {}
    for employee in data:
        key = f"{employee.get('rm_tran_no')}-{employee.get('erms_id')}"

        if key in seen:
            existing = seen[key]
            existing_reqs = existing.get("minor_reqs", "") or ""
            new_reqs = employee.get("minor_reqs", "") or ""

            # Merge and deduplicate minor_reqs
            combined_reqs = [existing_reqs, new_reqs]
            combined_reqs = [r for r in combined_reqs if r]
            combined_str = "; ".join(combined_reqs)

            # Deduplicate within the merged string
            req_list = [r.strip() for r in combined_str.split(";")]
            req_list = [r for r in req_list if r]
            deduped_list = []
            seen_reqs = set()
            for req in req_list:
                if req not in seen_reqs:
                    deduped_list.append(req)
                    seen_reqs.add(req)

            existing["minor_reqs"] = "; ".join(deduped_list)
        else:
            seen[key] = employee.copy()

    return list(seen.values())


def compute_missing_major(employee: dict) -> list[str]:
    """
    Compute list of missing major documents (SSS, Pag-IBIG, PhilHealth).
    A field is considered missing if it's an empty string or None.
    Returns list of human-readable labels for missing documents.
    """
    missing = []

    if not employee.get("rm_sss_no"):
        missing.append("SSS")
    if not employee.get("rm_pagibig_no"):
        missing.append("Pag-IBIG")
    if not employee.get("rm_phhealth"):
        missing.append("PhilHealth")

    return missing


def compute_missing_minor(employee: dict) -> list[str]:
    """
    Compute list of missing minor documents (universal + company-specific).
    A requirement is considered provided if it appears in the minor_reqs field.
    Returns list of human-readable labels for missing requirements.
    
    @param employee - Employee dict containing minor_reqs (semicolon-delimited string) and hr_company
    @return List of missing requirement names, empty if all requirements are satisfied
    """
    missing = []
    
    # Parse minor_reqs from semicolon-delimited string into a set for fast lookup
    minor_reqs_str = employee.get("minor_reqs", "") or ""
    provided_set = set()
    if minor_reqs_str:
        provided_list = [r.strip() for r in minor_reqs_str.split(";")]
        provided_set = set(req for req in provided_list if req)
    
    # Check universal requirements
    for req in UNIVERSAL_REQUIRED_REQS:
        if req not in provided_set:
            missing.append(req)
    
    # Check company-specific requirements if company matches
    company_name = employee.get("hr_company", "")
    if company_name and company_name in COMPANY_SPECIFIC_REQS:
        for req in COMPANY_SPECIFIC_REQS[company_name]:
            if req not in provided_set and req not in missing:
                missing.append(req)
    
    return missing


def sanitize_employee_data(employee: dict) -> dict:
    """
    Remove sensitive personally identifiable information (PII) from employee record.
    Removes: rm_sss_no, rm_pagibig_no, rm_phhealth
    Returns a new dict with PII fields removed.
    """
    sensitive_fields = {"rm_sss_no", "rm_pagibig_no", "rm_phhealth"}
    return {k: v for k, v in employee.items() if k not in sensitive_fields}


@router.get("/employee-requirements")
def get_employee_requirements(
    limit: int | None = Query(None, ge=1),
    offset: int | None = Query(None, ge=0),
    db: Session = Depends(get_db),
    caller = Depends(get_current_caller),  # UserModel | ExternalCaller
):
    # Resolve allowed BUs based on caller type
    if isinstance(caller, ExternalCaller):
        allowed_bus = caller.allowed_bus  # already resolved in token
        if allowed_bus == []:
            return []
    elif caller.account_type == "admin_account":
        allowed_bus = None  # sees everything
    else:
        allowed_bus = get_allowed_bus(caller, db)
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
        "total":  len(data),
        "data":   data,
    }


@router.get("/employee-requirements/missing-major")
def get_employee_requirements_missing_major():
    """
    Internal service-to-service endpoint.
    Returns employees missing at least one major document (SSS, Pag-IBIG, or PhilHealth).
    No authentication or BU filtering required.
    """
    try:
        response = httpx.get(EXTERNAL_API_URL, timeout=20.0)
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

    # Apply filters and transformations
    data = exclude_short_term(data)
    data = deduplicate_employees(data)

    # Filter to only employees with missing major documents and add missing_major field
    filtered_data = []
    for employee in data:
        missing_major = compute_missing_major(employee)
        if missing_major:
            employee["missing_major"] = missing_major
            filtered_data.append(employee)

    return {
        "status": "success",
        "total": len(filtered_data),
        "data": filtered_data,
    }


@router.get("/employee-requirements/missing-minor")
def get_employee_requirements_missing_minor():
    """
    Internal service-to-service endpoint.
    Returns employees missing at least one minor document (universal or company-specific).
    No authentication or BU filtering required.
    """
    try:
        response = httpx.get(EXTERNAL_API_URL, timeout=20.0)
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

    # Apply filters and transformations
    data = exclude_short_term(data)
    data = deduplicate_employees(data)

    # Filter to only employees with missing minor documents and add missing_minor field
    filtered_data = []
    for employee in data:
        missing_minor = compute_missing_minor(employee)
        if missing_minor:
            employee["missing_minor"] = missing_minor
            sanitized_employee = sanitize_employee_data(employee)
            filtered_data.append(sanitized_employee)

    return {
        "status": "success",
        "total": len(filtered_data),
        "data": filtered_data,
    }