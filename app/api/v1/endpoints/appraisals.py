from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_caller
from app.db.session import get_db
from app.models.appraisal import PerformanceAppraisalModel
from app.schemas.appraisal import (
	AppraisalListResponse,
	AppraisalRecordRead,
	DownloadUrlResponse,
	ExtensionDecisionPayload,
	FifthMonthSubmissionPayload,
	ThirdMonthSubmissionPayload,
	UploadUrlResponse,
)
from app.services.appraisal import (
	build_upload_url,
	build_download_url,
	fetch_all_employees,
	get_appraisal_record,
	list_appraisal_records,
	serialize_appraisal_record,
	serialize_for_regularization_record,
	submit_extension_decision,
	submit_fifth_month_decision,
	submit_third_month_decision,
)
from app.core.dependencies import get_current_caller, resolve_allowed_bus
from app.schemas.external import ExternalCaller
from app.services.appraisal import log_activity
import logging

router = APIRouter()

logger = logging.getLogger(__name__)

@router.get("/for-regularization", response_model=AppraisalListResponse)
def get_for_regularization(
    db: Session = Depends(get_db),
    current_user: ExternalCaller = Depends(get_current_caller),
):
    try:
        employees = fetch_all_employees()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    employee_map = {int(e.get("empidno")): e for e in employees if e.get("empidno") is not None}

    allowed_bus = resolve_allowed_bus(current_user)
    query = db.query(PerformanceAppraisalModel).filter(PerformanceAppraisalModel.appraisal_status == "REGULARIZED")
    if allowed_bus is not None:
        query = query.filter(PerformanceAppraisalModel.bu_tagging.in_(allowed_bus))
    records = query.order_by(PerformanceAppraisalModel.id.asc()).all()

    data = [serialize_for_regularization_record(r, employee_map.get(r.employee_id)) for r in records]
    return {"status": "success", "total": len(data), "data": data}


@router.get("/", response_model=AppraisalListResponse)
def list_appraisals(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: ExternalCaller = Depends(get_current_caller),
):
    try:
        employees = fetch_all_employees()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    employee_map = {int(e.get("empidno")): e for e in employees if e.get("empidno") is not None}
    records = list_appraisal_records(db, status_filter, allowed_bus=resolve_allowed_bus(current_user))
    data = [serialize_appraisal_record(r, employee_map.get(r.employee_id)) for r in records]
    return {"status": "success", "total": len(data), "data": data}


@router.get("/{employee_id}", response_model=AppraisalRecordRead)
def get_appraisal(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: ExternalCaller = Depends(get_current_caller),
):
    record = get_appraisal_record(db, employee_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Appraisal record not found")

    allowed_bus = resolve_allowed_bus(current_user)
    if allowed_bus is not None and record.bu_tagging not in allowed_bus:
        raise HTTPException(status_code=403, detail="Not authorized for this business unit")

    try:
        employees = fetch_all_employees()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    employee = next((e for e in employees if int(e.get("empidno", -1)) == employee_id), None)
    return serialize_appraisal_record(record, employee)

@router.post("/{employee_id}/third-month", response_model=AppraisalRecordRead)
def submit_third_month(
    employee_id: int,
    payload: ThirdMonthSubmissionPayload,
    db: Session = Depends(get_db),
    caller: ExternalCaller = Depends(get_current_caller),
):
    record = get_appraisal_record(db, employee_id)
    if record is None:
        log_activity(
            db, employee_id=employee_id, action="THIRD_MONTH_DECISION", status="FAILURE",
            actor_type="EXTERNAL", actor_id=caller.employee_id, bu_group=caller.bu_group,
            detail={"error": "record not found"},
        )
        db.commit()
        raise HTTPException(status_code=404, detail="Appraisal record not found")

    try:
        submit_third_month_decision(
            db, record,
            decision=payload.decision,
            appraisal_file_key=payload.appraisal_file_key,
            user_id=None,
        )
        log_activity(
            db, employee_id=employee_id, action="THIRD_MONTH_DECISION", status="SUCCESS",
            actor_type="EXTERNAL", actor_id=caller.employee_id, bu_group=caller.bu_group,
            detail={"decision": payload.decision, "file_key": payload.appraisal_file_key},
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        log_activity(
            db, employee_id=employee_id, action="THIRD_MONTH_DECISION", status="FAILURE",
            actor_type="EXTERNAL", actor_id=caller.employee_id, bu_group=caller.bu_group,
            detail={"decision": payload.decision, "error": str(exc)},
        )
        db.commit()
        logger.exception(
            "third_month_decision_error employee_id=%s caller_id=%s", employee_id, caller.employee_id,
        )
        raise HTTPException(status_code=500, detail="Failed to submit decision") from exc

    db.refresh(record)
    return serialize_appraisal_record(record)


@router.post("/{employee_id}/fifth-month", response_model=AppraisalRecordRead)
def submit_fifth_month(
	employee_id: int,
	payload: FifthMonthSubmissionPayload,
	db: Session = Depends(get_db),
	current_user: ExternalCaller = Depends(get_current_caller),
):
	record = get_appraisal_record(db, employee_id)
	if record is None:
		log_activity(
			db, employee_id=employee_id, action="FIFTH_MONTH_DECISION", status="FAILURE",
			actor_type="EXTERNAL", actor_id=str(current_user.employee_id), bu_group=None,
			detail={"error": "record not found"},
		)
		db.commit()
		raise HTTPException(status_code=404, detail="Appraisal record not found")

	try:
		submit_fifth_month_decision(
			db,
			record,
			decision=payload.decision,
			appraisal_file_key=payload.appraisal_file_key,
			user_id=None,
			extension_until=payload.extension_until,
		)
		log_activity(
			db, employee_id=employee_id, action="FIFTH_MONTH_DECISION", status="SUCCESS",
			actor_type="EXTERNAL", actor_id=str(current_user.employee_id), bu_group=record.bu_tagging,
			detail={"decision": payload.decision, "file_key": payload.appraisal_file_key},
		)
		db.commit()
	except Exception as exc:
		db.rollback()
		log_activity(
			db, employee_id=employee_id, action="FIFTH_MONTH_DECISION", status="FAILURE",
			actor_type="EXTERNAL", actor_id=str(current_user.employee_id), bu_group=record.bu_tagging,
			detail={"decision": payload.decision, "error": str(exc)},
		)
		db.commit()
		logger.exception(
			"fifth_month_decision_error employee_id=%s caller_id=%s", employee_id, current_user.employee_id,
		)
		raise HTTPException(status_code=500, detail="Failed to submit decision") from exc

	db.refresh(record)
	return serialize_appraisal_record(record)


@router.post("/{employee_id}/extension-decision", response_model=AppraisalRecordRead)
def submit_extension(
    employee_id: int,
    payload: ExtensionDecisionPayload,
    db: Session = Depends(get_db),
    current_user: ExternalCaller = Depends(get_current_caller),
):
    record = get_appraisal_record(db, employee_id)
    if record is None:
        log_activity(
            db, employee_id=employee_id, action="EXTENSION_DECISION", status="FAILURE",
            actor_type="EXTERNAL", actor_id=str(current_user.employee_id), bu_group=None,
            detail={"error": "record not found"},
        )
        db.commit()
        raise HTTPException(status_code=404, detail="Appraisal record not found")

    try:
        submit_extension_decision(
            db,
            record,
            decision=payload.decision,
            appraisal_file_key=payload.appraisal_file_key,
            extension_until=payload.extension_until,
            user_id=None,
        )
        log_activity(
            db, employee_id=employee_id, action="EXTENSION_DECISION", status="SUCCESS",
            actor_type="EXTERNAL", actor_id=str(current_user.employee_id), bu_group=record.bu_tagging,
            detail={
                "decision": payload.decision,
                "file_key": payload.appraisal_file_key,
                "extension_until": str(payload.extension_until) if payload.extension_until else None,
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        log_activity(
            db, employee_id=employee_id, action="EXTENSION_DECISION", status="FAILURE",
            actor_type="EXTERNAL", actor_id=str(current_user.employee_id), bu_group=record.bu_tagging,
            detail={"decision": payload.decision, "error": str(exc)},
        )
        db.commit()
        logger.exception(
            "extension_decision_error employee_id=%s caller_id=%s", employee_id, current_user.employee_id,
        )
        raise HTTPException(status_code=500, detail="Failed to submit decision") from exc

    db.refresh(record)
    return serialize_appraisal_record(record)


@router.post("/{employee_id}/upload-url", response_model=UploadUrlResponse)
def get_upload_url(
    employee_id: int,
    content_type: str = Query("application/pdf"),
    db: Session = Depends(get_db),
    current_user: ExternalCaller = Depends(get_current_caller),
):
    record = get_appraisal_record(db, employee_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Appraisal record not found")

    ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    try:
        upload_url, file_key = build_upload_url(record, "appraisal-file")
        log_activity(
            db, employee_id=employee_id, action="UPLOAD_URL_ISSUED", status="SUCCESS",
            actor_type="EXTERNAL", actor_id=str(current_user.employee_id), bu_group=record.bu_tagging,
            detail={"content_type": content_type, "file_key": file_key},
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        log_activity(
            db, employee_id=employee_id, action="UPLOAD_URL_ISSUED", status="FAILURE",
            actor_type="EXTERNAL", actor_id=str(current_user.employee_id), bu_group=record.bu_tagging,
            detail={"content_type": content_type, "error": str(exc)},
        )
        db.commit()
        logger.exception(
            "upload_url_error employee_id=%s caller_id=%s", employee_id, current_user.employee_id,
        )
        raise HTTPException(status_code=500, detail="Failed to generate upload URL") from exc

    return {"upload_url": upload_url, "file_key": file_key}


@router.get("/{employee_id}/files/{file_key:path}/download-url", response_model=DownloadUrlResponse)
def get_download_url(
    employee_id: int,
    file_key: str,
    db: Session = Depends(get_db),
    current_user: ExternalCaller = Depends(get_current_caller),
):
    record = get_appraisal_record(db, employee_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Appraisal record not found")

    download_url = build_download_url(file_key)
    return {"download_url": download_url}