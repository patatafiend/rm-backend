from datetime import datetime, timezone
from typing import Any

import httpx
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import get_current_user
from app.models.user import UserModel
from app.core.dependencies import get_current_caller

router = APIRouter()

EXTERNAL_API_URL = "https://cmiitdept.com/hr/api_analytics_main_pooling"

VALID_STATUSES = {"Applicant", "For Onboarding", "For Medical", "Failed Drug test", "Onboarded"}
FUNNEL_ORDER = ["Applicant", "For Medical", "For Onboarding", "Onboarded"]

# ---------------------------------------------------------------------------
# Simple in-memory TTL cache
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[Any, datetime]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


def _cache_get(key: str) -> Any | None:
    if key in _cache:
        value, ts = _cache[key]
        if (datetime.now(timezone.utc) - ts).total_seconds() < _CACHE_TTL_SECONDS:
            return value
        del _cache[key]
    return None


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = (value, datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# ETL helpers
# ---------------------------------------------------------------------------

STATUS_NORMALIZE = {
    "for medical": "For Medical",
    "for onboarding": "For Onboarding",
    "failed drug test": "Failed Drug test",
    "applicant": "Applicant",
    "onboarded": "Onboarded",
}

def normalize_statuses(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["rm_job_status"] = (
        df["rm_job_status"]
        .str.strip()
        .str.lower()
        .map(lambda x: STATUS_NORMALIZE.get(x, x) if pd.notna(x) else x)
    )
    return df

def fetch_raw() -> list[dict]:
    try:
        response = httpx.get(EXTERNAL_API_URL, timeout=30.0)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="External API request failed") from exc

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="External API returned an error")

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Invalid external API response") from exc

    if not isinstance(payload, dict) or "data" not in payload:
        raise HTTPException(status_code=502, detail="Unexpected external API response shape")

    return payload["data"]


def filter_statuses(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["rm_job_status"].isin(VALID_STATUSES)].copy()


def flag_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["_is_duplicate"] = df.duplicated(subset=["rm_tran_no"], keep=False)
    return df


def build_data_quality(df: pd.DataFrame) -> dict:
    missing_encode = int(df["rm_encode_date"].isna().sum()) if "rm_encode_date" in df.columns else len(df)
    missing_contract = int(df[df["rm_job_status"] == "Onboarded"]["admin_condate"].isna().sum()) if "admin_condate" in df.columns else 0

    duplicate_count = int(df.duplicated(subset=["rm_tran_no"], keep=False).sum())

    original_count = len(df) + len(df)  # before + after — just use df for the filtered count
    total_raw = len(df)
    invalid_status_count = 0  # already filtered before calling this

    return {
        "missing_encode_date": missing_encode,
        "missing_contract_date": missing_contract,
        "duplicate_tran_no_count": duplicate_count,
        "invalid_status_count": invalid_status_count,
        "total_filtered": total_raw,
    }


def get_or_fetch_df(refresh: bool) -> pd.DataFrame:
    cache_key = "raw_df"
    if not refresh:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    raw = fetch_raw()
    df = pd.DataFrame(raw)

    if df.empty:
        _cache_set(cache_key, df)
        return df
    
    df = normalize_statuses(df)
    df = filter_statuses(df)

    # Parse dates
    if "rm_encode_date" in df.columns:
        df["rm_encode_date"] = pd.to_datetime(df["rm_encode_date"], errors="coerce")
    if "admin_condate" in df.columns:
        df["admin_condate"] = pd.to_datetime(df["admin_condate"], errors="coerce")

    _cache_set(cache_key, df)
    return df


def make_meta(df: pd.DataFrame) -> dict:
    return {
        "filtered_count": len(df),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_quality_flags": build_data_quality(df),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status-counts")
def get_status_counts(
    refresh: bool = Query(False),
    bu: str | None = Query(None),
    _user = Depends(get_current_caller),
):
    cache_key = f"status_counts:{refresh}:{bu}"
    if not refresh:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    df = get_or_fetch_df(refresh)
    if bu and not df.empty:
        df = df[df["bu_tagging"] == bu]

    counts = df["rm_job_status"].value_counts().to_dict() if not df.empty else {}
    result = {
        "meta": make_meta(df),
        "data": [{"status": k, "count": int(v)} for k, v in counts.items()],
    }
    _cache_set(cache_key, result)
    return result


@router.get("/funnel")
def get_funnel(
    refresh: bool = Query(False),
    bu: str | None = Query(None),
    _user = Depends(get_current_caller),
):
    cache_key = f"funnel:{refresh}:{bu}"
    if not refresh:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    df = get_or_fetch_df(refresh)
    if bu and not df.empty:
        df = df[df["bu_tagging"] == bu]

    stages = []
    for status in FUNNEL_ORDER:
        count = int((df["rm_job_status"] == status).sum()) if not df.empty else 0
        stages.append({"stage": status, "count": count})

    # Stage-to-stage conversion rates
    for i, stage in enumerate(stages):
        if i == 0:
            stage["conversion_from_prev"] = None
            stage["cumulative_conversion"] = 1.0
        else:
            prev_count = stages[i - 1]["count"]
            raw_conversion = stage["count"] / prev_count if prev_count > 0 else 0.0
            stage["conversion_from_prev"] = round(min(raw_conversion, 1.0), 4)
            first_count = stages[0]["count"]
            raw_cumulative = stage["count"] / first_count if first_count > 0 else 0.0
            stage["cumulative_conversion"] = round(min(raw_cumulative, 1.0), 4)

    result = {
        "meta": make_meta(df),
        "data": stages,
        "note": "",
    }
    _cache_set(cache_key, result)
    return result


@router.get("/time-metrics")
def get_time_metrics(
    refresh: bool = Query(False),
    bu: str | None = Query(None),
    _user = Depends(get_current_caller),
):
    cache_key = f"time_metrics:{refresh}:{bu}"
    if not refresh:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    df = get_or_fetch_df(refresh)
    meta = make_meta(df)

    if bu and not df.empty:
        df = df[df["bu_tagging"] == bu]

    if df.empty or "rm_encode_date" not in df.columns or "admin_condate" not in df.columns:
        result = {
            "meta": meta,
            "data": [],
            "note": "Time metrics unavailable: missing rm_encode_date or admin_condate fields.",
        }
        _cache_set(cache_key, result)
        return result

    onboarded = df[
        (df["rm_job_status"] == "Onboarded")
        & df["rm_encode_date"].notna()
        & df["admin_condate"].notna()
    ].copy()

    if onboarded.empty:
        result = {
            "meta": meta,
            "data": [],
            "note": "No onboarded rows with both encode date and contract date.",
        }
        _cache_set(cache_key, result)
        return result

    onboarded["days_to_onboard"] = (
        onboarded["admin_condate"] - onboarded["rm_encode_date"]
    ).dt.days

    valid = onboarded[onboarded["days_to_onboard"] >= 0]["days_to_onboard"]

    metrics = {
        "stage": "Encode → Onboarded",
        "sample_size": int(len(valid)),
        "mean_days": round(float(valid.mean()), 2) if not valid.empty else None,
        "median_days": round(float(valid.median()), 2) if not valid.empty else None,
        "min_days": int(valid.min()) if not valid.empty else None,
        "max_days": int(valid.max()) if not valid.empty else None,
    }

    result = {
        "meta": meta,
        "data": [metrics],
        "note": "",
    }
    _cache_set(cache_key, result)
    return result


@router.get("/weekly-trend")
def get_weekly_trend(
    weeks: int = Query(12, ge=1, le=52),
    refresh: bool = Query(False),
    bu: str | None = Query(None),
    _user = Depends(get_current_caller),
):
    cache_key = f"weekly_trend:{weeks}:{refresh}:{bu}"
    if not refresh:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    df = get_or_fetch_df(refresh)
    meta = make_meta(df)

    if bu and not df.empty:
        df = df[df["bu_tagging"] == bu]

    if df.empty or "rm_encode_date" not in df.columns:
        result = {"meta": meta, "data": []}
        _cache_set(cache_key, result)
        return result

    dated = df[df["rm_encode_date"].notna()].copy()
    dated["iso_week"] = dated["rm_encode_date"].dt.strftime("%G-W%V")

    weekly = (
        dated.groupby("iso_week")
        .size()
        .reset_index(name="count")
        .sort_values("iso_week", ascending=False)
        .head(weeks)
        .sort_values("iso_week")
    )

    result = {
        "meta": meta,
        "data": weekly.to_dict(orient="records"),
    }
    _cache_set(cache_key, result)
    return result


@router.get("/raw")
def get_raw(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    bu: str | None = Query(None),
    company: str | None = Query(None),
    status: str | None = Query(None),
    refresh: bool = Query(False),
    _user = Depends(get_current_caller),
):
    df = get_or_fetch_df(refresh)
    meta = make_meta(df)

    if not df.empty:
        if bu:
            df = df[df["bu_tagging"] == bu]
        if company:
            df = df[df["hr_company"] == company]
        if status and status in VALID_STATUSES:
            df = df[df["rm_job_status"] == status]

    total = len(df)
    page = df.iloc[offset: offset + limit]

    # Serialize: convert timestamps back to ISO strings
    records = []
    for _, row in page.iterrows():
        rec = row.where(pd.notna(row), other=None).to_dict()
        for k, v in rec.items():
            if isinstance(v, pd.Timestamp):
                rec[k] = v.isoformat()
        records.append(rec)

    meta["total"] = total
    meta["limit"] = limit
    meta["offset"] = offset

    return {"meta": meta, "data": records}

@router.get("/bu-list")
def get_bu_list(
    refresh: bool = Query(False),
    _user = Depends(get_current_caller),
):
    cache_key = f"bu_list:{refresh}"
    if not refresh:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    df = get_or_fetch_df(refresh)
    bus = sorted(df["bu_tagging"].dropna().unique().tolist()) if not df.empty else []
    result = {"data": bus}
    _cache_set(cache_key, result)
    return result