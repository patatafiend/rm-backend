from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import httpx
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
from app.core.s3 import get_s3_client
from app.core.config import settings
from app.models.appraisal import NotificationModel, PerformanceAppraisalModel, ExtensionRecordModel
from uuid import uuid4

EXTERNAL_API_URL = "https://cmiitdept.com/hr/api_onboarded_minor.php"
ELIGIBLE_STATUSES = {"PROBATIONARY"}


def now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"Unsupported date value: {value!r}")


def fetch_all_employees() -> list[dict]:
    try:
        response = httpx.get(EXTERNAL_API_URL, timeout=20.0)
    except httpx.RequestError as exc:
        raise RuntimeError("External API request failed") from exc

    if response.status_code != 200:
        raise RuntimeError("External API returned an error")

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Invalid external API response") from exc

    if not isinstance(payload, dict) or "data" not in payload:
        raise RuntimeError("Unexpected external API response shape")

    data = payload["data"]
    if not isinstance(data, list):
        raise RuntimeError("Unexpected external API data shape")

    return data


def add_months(base_date: date | datetime | str, months: int) -> date:
    return _coerce_date(base_date) + relativedelta(months=months)


def compute_calendar_months_since(base_date: date | datetime | str, as_of: date | datetime | str | None = None) -> int:
    start_date = _coerce_date(base_date)
    end_date = _coerce_date(as_of or date.today())
    delta = relativedelta(end_date, start_date)
    return delta.years * 12 + delta.months


def get_or_create_appraisal_record(db: Session, employee: dict) -> PerformanceAppraisalModel:
    rm_tran_no = int(employee["rm_tran_no"])
    record = db.query(PerformanceAppraisalModel).filter(PerformanceAppraisalModel.rm_tran_no == rm_tran_no).first()
    if record:
        return record

    record = PerformanceAppraisalModel(
        rm_tran_no=rm_tran_no,
        erms_id=int(employee["erms_id"]),
        contract_sdate=_coerce_date(employee["contract_sdate"]),
        bu_tagging=employee.get("bu_tagging", ""),
    )
    db.add(record)
    db.flush()
    return record


def create_notification(
    db: Session,
    *,
    recipient_type: str,
    recipient_value: str,
    milestone: str,
    rm_tran_no: int,
    message: str,
) -> NotificationModel:
    notification = NotificationModel(
        recipient_type=recipient_type,
        recipient_value=recipient_value,
        milestone=milestone,
        rm_tran_no=rm_tran_no,
        message=message,
    )
    db.add(notification)
    return notification


def build_employee_name(employee: dict) -> str:
    parts = [
        str(employee.get("rm_first_name", "")).strip(),
        str(employee.get("rm_middle_name", "")).strip(),
        str(employee.get("rm_lastname", "")).strip(),
        str(employee.get("rm_other_name", "")).strip(),
    ]
    return " ".join(part for part in parts if part)

def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()

def serialize_appraisal_record(record: PerformanceAppraisalModel, employee: dict | None = None) -> dict:
    payload = {
        "rm_tran_no": record.rm_tran_no,
        "erms_id": record.erms_id,
        "contract_sdate": record.contract_sdate.isoformat() if record.contract_sdate else None,
        "bu_tagging": record.bu_tagging,
        "third_month_due_date": record.third_month_due_date.isoformat() if record.third_month_due_date else None,
        "third_month_decision": record.third_month_decision,
        "third_month_notified_at": record.third_month_notified_at.isoformat() if record.third_month_notified_at else None,
        "fifth_month_due_date": record.fifth_month_due_date.isoformat() if record.fifth_month_due_date else None,
        "fifth_month_decision": record.fifth_month_decision,
        "fifth_month_notified_at": record.fifth_month_notified_at.isoformat() if record.fifth_month_notified_at else None,
        "third_month_appraisal_file_key": record.third_month_appraisal_file_key,
        "third_month_decided_at": _iso_utc(record.third_month_decided_at),
        "fifth_month_appraisal_file_key": record.fifth_month_appraisal_file_key,
        "fifth_month_decided_at": _iso_utc(record.fifth_month_decided_at),
        "sixth_month_check_date": record.sixth_month_check_date.isoformat() if record.sixth_month_check_date else None,
        "confirmed_at": record.confirmed_at.isoformat() if record.confirmed_at else None,
        "appraisal_status": record.appraisal_status,
        "failsafe_reason": record.failsafe_reason,
        "failsafe_triggered_at": record.failsafe_triggered_at.isoformat() if record.failsafe_triggered_at else None,
        "extension_records":[serialize_extension_record(e) for e in record.extension_records],
    }

    if employee:
        payload.update(
            {
                "employee_name": build_employee_name(employee),
                "hr_company": employee.get("hr_company"),
                "hr_client": employee.get("hr_client"),
                "rm_pos_applied": employee.get("rm_pos_applied"),
                "emp_status": employee.get("emp_status"),
            }
        )

    return payload


def serialize_for_regularization_record(record: PerformanceAppraisalModel, employee: dict | None = None) -> dict:
    return serialize_appraisal_record(record, employee)


def get_appraisal_record(db: Session, rm_tran_no: int) -> PerformanceAppraisalModel | None:
    return db.query(PerformanceAppraisalModel).filter(PerformanceAppraisalModel.rm_tran_no == rm_tran_no).first()


def list_appraisal_records(db: Session, status: str | None = None) -> list[PerformanceAppraisalModel]:
    query = db.query(PerformanceAppraisalModel).filter(
        PerformanceAppraisalModel.third_month_notified_at.isnot(None)
    )

    if status:
        query = query.filter(PerformanceAppraisalModel.appraisal_status == status)

    return query.order_by(PerformanceAppraisalModel.id.asc()).all()


def submit_third_month_decision(
    db: Session,
    record: PerformanceAppraisalModel,
    *,
    decision: str,
    appraisal_file_key: str,
    user_id: int,
) -> PerformanceAppraisalModel:
    record.third_month_decision = decision
    record.third_month_appraisal_file_key = appraisal_file_key
    record.third_month_decided_by = user_id
    record.third_month_decided_at = now()
    record.appraisal_status = "FOR_REGULARIZATION"

    if decision == "NON_REGULARIZATION":
        record.appraisal_status = "NON_REGULARIZED"
        record.confirmed_at = now()

    db.flush()
    return record


def submit_fifth_month_decision(
    db: Session,
    record: PerformanceAppraisalModel,
    *,
    decision: str,
    appraisal_file_key: str | None = None,
    user_id: int,
    extension_until: date | None = None,
) -> PerformanceAppraisalModel:
    record.fifth_month_decision = decision
    record.fifth_month_appraisal_file_key = appraisal_file_key
    record.fifth_month_decided_by = user_id
    record.fifth_month_decided_at = now()

    if decision == "EXTENSION":
        create_extension_record(db, record, extension_until=extension_until, granted_by=user_id)
    elif decision == "REGULARIZATION":
        record.appraisal_status = "REGULARIZED"
        record.confirmed_at = now()
    elif decision == "NON_REGULARIZATION":
        record.appraisal_status = "NON_REGULARIZED"
        record.confirmed_at = now()

    db.flush()
    return record


def submit_extension_decision(
    db: Session,
    record: PerformanceAppraisalModel,
    *,
    decision: str,
    user_id: int,
    appraisal_file_key: str | None = None,
    extension_until: date | None = None,
) -> PerformanceAppraisalModel:
    latest = get_latest_extension_record(db, record.id)
    if latest is None:
        raise ValueError("No active extension record found for this appraisal")

    latest.decision = decision
    latest.appraisal_file_key = appraisal_file_key
    latest.decided_by = user_id
    latest.decided_at = now()

    if decision == "EXTENSION":
        if extension_until is None:
            raise ValueError("extension_until is required when extending again")
        create_extension_record(db, record, extension_until=extension_until, granted_by=user_id)
    elif decision == "REGULARIZATION":
        record.appraisal_status = "REGULARIZED"
        record.confirmed_at = now()
    else:
        record.appraisal_status = "NON_REGULARIZED"
        record.confirmed_at = now()

    db.flush()
    return record


def build_upload_url(record, category: str) -> tuple[str, str]:
    file_key = (
        f"uploads/{settings.ENV}/appraisals/{record.rm_tran_no}/"
        f"{category}/{uuid4()}"
    )
    client = get_s3_client()
    upload_url = client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.S3_BUCKET_NAME,
            "Key": file_key,
        },
        ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRY,
    )
    return upload_url, file_key


_EXTENSIONS = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}

def _extension_for(content_type: str) -> str:
    try:
        return _EXTENSIONS[content_type]
    except KeyError:
        raise ValueError(f"Unsupported content type: {content_type}")

def build_download_url(file_key: str) -> str:
    client = get_s3_client()
    return client.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": settings.S3_BUCKET_NAME,
            "Key": file_key,
        },
        ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRY,
    )


def run_appraisal_cycle_job(db: Session) -> None:
    all_employees = fetch_all_employees()
    by_tran_no = {
        int(employee["rm_tran_no"]): employee
        for employee in all_employees
        if employee.get("rm_tran_no") is not None
    }
    eligible = [
        employee
        for employee in all_employees
        if str(employee.get("emp_status", "")).strip().upper() in ELIGIBLE_STATUSES
    ]

    for employee in eligible:
        record = get_or_create_appraisal_record(db, employee)
        months = compute_calendar_months_since(record.contract_sdate)
        today = date.today()

        if months < 3:
            db.flush()
            continue

        if record.sixth_month_check_date is None:
            record.sixth_month_check_date = add_months(record.contract_sdate, 6)

        if months >= 3 and record.third_month_notified_at is None:
            record.third_month_due_date = add_months(record.contract_sdate, 3)
            record.third_month_notified_at = now()
            create_notification(
                db,
                recipient_type="BU_GROUP",
                recipient_value=record.bu_tagging,
                milestone="3RD_MONTH_APPRAISAL_DUE",
                rm_tran_no=record.rm_tran_no,
                message="Third month appraisal is due.",
            )

        if months >= 5 and record.third_month_decision is None and record.appraisal_status == "PENDING":
            record.third_month_decision = "NO_APPRAISAL"
            record.third_month_decided_at = now()
            record.failsafe_reason = "NO_3RD_MONTH_APPRAISAL"
            create_notification(
                db,
                recipient_type="BU_GROUP",
                recipient_value=record.bu_tagging,
                milestone="NON_COMPLIANCE_NO_3RD_MONTH_APPRAISAL",
                rm_tran_no=record.rm_tran_no,
                message="No third month appraisal has been submitted.",
            )
            create_notification(
                db,
                recipient_type="ROLE",
                recipient_value="HRBP",
                milestone="NON_COMPLIANCE_NO_3RD_MONTH_APPRAISAL",
                rm_tran_no=record.rm_tran_no,
                message="No third month appraisal has been submitted.",
            )

        if months >= 5 and record.fifth_month_notified_at is None:
            record.fifth_month_due_date = add_months(record.contract_sdate, 5)
            record.fifth_month_notified_at = now()
            create_notification(
                db,
                recipient_type="BU_GROUP",
                recipient_value=record.bu_tagging,
                milestone="5TH_MONTH_APPRAISAL_DUE",
                rm_tran_no=record.rm_tran_no,
                message="Fifth month appraisal is due.",
            )

        if record.fifth_month_decision == "EXTENSION" and record.appraisal_status == "PENDING":
            latest_ext = get_latest_extension_record(db, record.id)
            if (
                latest_ext is not None
                and latest_ext.extension_until
                and today >= latest_ext.extension_until
                and latest_ext.decision is None
            ):
                record.appraisal_status = "FOR_REGULARIZATION"
                record.failsafe_triggered = True
                record.failsafe_triggered_at = now()
                record.failsafe_reason = "EXTENSION_UNRESOLVED"
                create_notification(
                    db,
                    recipient_type="BU_GROUP",
                    recipient_value=record.bu_tagging,
                    milestone="NON_COMPLIANCE_EXTENSION_UNRESOLVED_AUTO_REGULARIZED",
                    rm_tran_no=record.rm_tran_no,
                    message="Extension window elapsed without a final decision.",
                )
                create_notification(
                    db,
                    recipient_type="ROLE",
                    recipient_value="HRBP",
                    milestone="NON_COMPLIANCE_EXTENSION_UNRESOLVED_AUTO_REGULARIZED",
                    rm_tran_no=record.rm_tran_no,
                    message="Extension window elapsed without a final decision.",
                )

        if months >= 6 and record.appraisal_status == "PENDING" and record.fifth_month_decision is None:
            record.appraisal_status = "FOR_REGULARIZATION"
            record.failsafe_triggered = True
            record.failsafe_triggered_at = now()
            record.fifth_month_decision = "NO_APPRAISAL"
            record.fifth_month_decided_at = now()
            record.failsafe_reason = (
                    "NO_3RD_MONTH_APPRAISAL"
                    if record.third_month_decision in (None, "NO_APPRAISAL")
                    else "NO_5TH_MONTH_DECISION"
            )
            create_notification(
                db,
                recipient_type="BU_GROUP",
                recipient_value=record.bu_tagging,
                milestone="NON_COMPLIANCE_AUTO_REGULARIZED",
                rm_tran_no=record.rm_tran_no,
                message="Probationary appraisal has reached the fail-safe window.",
            )
            create_notification(
                db,
                recipient_type="ROLE",
                recipient_value="HRBP",
                milestone="NON_COMPLIANCE_AUTO_REGULARIZED",
                rm_tran_no=record.rm_tran_no,
                message="Probationary appraisal has reached the fail-safe window.",
            )

        db.flush()

    reconcile_resolved_employees(db, by_tran_no)
    db.commit()


def reconcile_resolved_employees(db: Session, by_tran_no: dict[int, dict]) -> None:
    open_records = (
        db.query(PerformanceAppraisalModel)
        .filter(PerformanceAppraisalModel.appraisal_status.in_(["PENDING", "FOR_REGULARIZATION"]))
        .all()
    )

    for record in open_records:
        employee = by_tran_no.get(record.rm_tran_no)

        if employee is None:
            record.appraisal_status = "NEEDS_REVIEW"
            continue

        status = str(employee.get("emp_status", "")).strip().upper()
        if status == "REGULAR":
            record.appraisal_status = "FOR_REGULARIZATION"
            record.confirmed_at = now()
        elif status not in ELIGIBLE_STATUSES:
            record.appraisal_status = "NEEDS_REVIEW"

def create_extension_record(
    db: Session,
    record: PerformanceAppraisalModel,
    *,
    extension_until: date,
    granted_by: int | None = None,
) -> ExtensionRecordModel:
    existing_count = (
        db.query(ExtensionRecordModel)
        .filter(ExtensionRecordModel.appraisal_id == record.id)
        .count()
    )
    extension = ExtensionRecordModel(
        appraisal_id=record.id,
        sequence=existing_count + 1,
        extension_until=extension_until,
        granted_by=granted_by,
    )
    db.add(extension)
    db.flush()
    return extension


def get_latest_extension_record(db: Session, appraisal_id: int) -> ExtensionRecordModel | None:
    return (
        db.query(ExtensionRecordModel)
        .filter(ExtensionRecordModel.appraisal_id == appraisal_id)
        .order_by(ExtensionRecordModel.sequence.desc())
        .first()
    )

def serialize_extension_record(ext: ExtensionRecordModel) -> dict:
    return {
        "id": ext.id,
        "sequence": ext.sequence,
        "extension_until": ext.extension_until.isoformat() if ext.extension_until else None,
        "granted_at": _iso_utc(ext.granted_at),
        "decision": ext.decision,
        "appraisal_file_key": ext.appraisal_file_key,
        "decided_at": _iso_utc(ext.decided_at),
    }