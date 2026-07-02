from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import httpx
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.models.appraisal import NotificationModel, PerformanceAppraisalModel

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
        "extension_until": record.extension_until.isoformat() if record.extension_until else None,
        "extension_final_decision": record.extension_final_decision,
        "appraisal_status": record.appraisal_status,
        "failsafe_reason": record.failsafe_reason,
        "failsafe_triggered_at": record.failsafe_triggered_at.isoformat() if record.failsafe_triggered_at else None,
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
    query = db.query(PerformanceAppraisalModel)

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
    appraisal_file_key: str,
    user_id: int,
    extension_until: date | None = None,
) -> PerformanceAppraisalModel:
    record.fifth_month_decision = decision
    record.fifth_month_appraisal_file_key = appraisal_file_key
    record.fifth_month_decided_by = user_id
    record.fifth_month_decided_at = now()

    if decision == "EXTENSION":
        record.extension_until = extension_until
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
) -> PerformanceAppraisalModel:
    record.extension_final_decision = decision
    record.extension_decided_by = user_id
    record.extension_decided_at = now()

    if decision == "REGULARIZATION":
        record.appraisal_status = "REGULARIZED"
    else:
        record.appraisal_status = "NON_REGULARIZED"

    record.confirmed_at = now()
    db.flush()
    return record


def build_upload_placeholder(record: PerformanceAppraisalModel, suffix: str) -> tuple[str, str]:
    file_key = f"appraisals/{record.rm_tran_no}/{suffix}"
    upload_url = ""
    return upload_url, file_key


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

        if (
            record.fifth_month_decision == "EXTENSION"
            and record.extension_until
            and today >= record.extension_until
            and record.extension_final_decision is None
            and record.appraisal_status == "PENDING"
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
            record.failsafe_reason = (
                "NO_3RD_MONTH_APPRAISAL" if record.third_month_decision is None else "NO_5TH_MONTH_DECISION"
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
            record.appraisal_status = "REGULARIZED"
            record.confirmed_at = now()
        elif status not in ELIGIBLE_STATUSES:
            record.appraisal_status = "NEEDS_REVIEW"