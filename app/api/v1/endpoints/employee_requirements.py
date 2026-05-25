from fastapi import APIRouter, Depends, HTTPException, Query
import httpx

from app.core.dependencies import get_current_user

router = APIRouter()

EXTERNAL_API_URL = "https://cmiitdept.com/hr/api_onboarded_minor.php"


@router.get("/employee-requirements", dependencies=[Depends(get_current_user)])
def get_employee_requirements(
    limit: int | None = Query(None, ge=1),
    offset: int | None = Query(None, ge=0),
):
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
        return response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Invalid external API response") from exc
