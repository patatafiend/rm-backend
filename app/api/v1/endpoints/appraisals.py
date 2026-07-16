from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_caller
from app.db.session import get_db
from app.models.appraisal import PerformanceAppraisalModel
from app.models.user import UserModel
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

router = APIRouter()


@router.get("/for-regularization")
def get_for_regularization(
	db: Session = Depends(get_db),
	response_model=AppraisalListResponse
):
	try:
		employees = fetch_all_employees()
	except RuntimeError as exc:
		raise HTTPException(status_code=502, detail=str(exc)) from exc

	employee_map = {int(employee.get("rm_tran_no")): employee for employee in employees if employee.get("rm_tran_no") is not None}

	records = (
		db.query(PerformanceAppraisalModel)
		.filter(PerformanceAppraisalModel.appraisal_status == "REGULARIZED")
		.order_by(PerformanceAppraisalModel.id.asc())
		.all()
	)

	data = [serialize_for_regularization_record(record, employee_map.get(record.rm_tran_no)) for record in records]

	return {
		"status": "success",
		"total": len(data),
		"data": data,
	}


@router.get("/", response_model=AppraisalListResponse)
def list_appraisals(
	status_filter: str | None = Query(None, alias="status"),
	db: Session = Depends(get_db),
	current_user: UserModel = Depends(get_current_caller),
):
	try:
		employees = fetch_all_employees()
	except RuntimeError as exc:
		raise HTTPException(status_code=502, detail=str(exc)) from exc

	employee_map = {
		int(employee.get("rm_tran_no")): employee
		for employee in employees
		if employee.get("rm_tran_no") is not None
	}
	records = list_appraisal_records(db, status_filter)
	data = [serialize_appraisal_record(record, employee_map.get(record.rm_tran_no)) for record in records]
	return {"status": "success", "total": len(data), "data": data}


@router.get("/{rm_tran_no}", response_model=AppraisalRecordRead)
def get_appraisal(
	rm_tran_no: int,
	db: Session = Depends(get_db),
	current_user: UserModel = Depends(get_current_caller),
):
	try:
		employees = fetch_all_employees()
	except RuntimeError as exc:
		raise HTTPException(status_code=502, detail=str(exc)) from exc

	record = get_appraisal_record(db, rm_tran_no)
	if record is None:
		raise HTTPException(status_code=404, detail="Appraisal record not found")

	employee = next((item for item in employees if int(item.get("rm_tran_no", -1)) == rm_tran_no), None)
	return serialize_appraisal_record(record, employee)


@router.post("/{rm_tran_no}/third-month", response_model=AppraisalRecordRead)
def submit_third_month(
	rm_tran_no: int,
	payload: ThirdMonthSubmissionPayload,
	db: Session = Depends(get_db),
	current_user: UserModel = Depends(get_current_caller),
):
	record = get_appraisal_record(db, rm_tran_no)
	if record is None:
		raise HTTPException(status_code=404, detail="Appraisal record not found")

	submit_third_month_decision(
		db,
		record,
		decision=payload.decision,
		appraisal_file_key=payload.appraisal_file_key,
		user_id=current_user.id,
	)
	db.commit()
	db.refresh(record)
	return serialize_appraisal_record(record)


@router.post("/{rm_tran_no}/fifth-month", response_model=AppraisalRecordRead)
def submit_fifth_month(
	rm_tran_no: int,
	payload: FifthMonthSubmissionPayload,
	db: Session = Depends(get_db),
	current_user: UserModel = Depends(get_current_caller),
):
	record = get_appraisal_record(db, rm_tran_no)
	if record is None:
		raise HTTPException(status_code=404, detail="Appraisal record not found")

	submit_fifth_month_decision(
		db,
		record,
		decision=payload.decision,
		appraisal_file_key=payload.appraisal_file_key,
		user_id=current_user.id,
		extension_until=payload.extension_until,
	)
	db.commit()
	db.refresh(record)
	return serialize_appraisal_record(record)


@router.post("/{rm_tran_no}/extension-decision", response_model=AppraisalRecordRead)
def submit_extension(
    rm_tran_no: int,
    payload: ExtensionDecisionPayload,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_caller),
):
    record = get_appraisal_record(db, rm_tran_no)
    if record is None:
        raise HTTPException(status_code=404, detail="Appraisal record not found")

    submit_extension_decision(
        db,
        record,
        decision=payload.decision,
        appraisal_file_key=payload.appraisal_file_key,
        extension_until=payload.extension_until,
        user_id=current_user.id,
    )
    db.commit()
    db.refresh(record)
    return serialize_appraisal_record(record)



@router.post("/{rm_tran_no}/upload-url", response_model=UploadUrlResponse)
def get_upload_url(
    rm_tran_no: int,
    content_type: str = Query("application/pdf"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_caller),
):
    record = get_appraisal_record(db, rm_tran_no)
    if record is None:
        raise HTTPException(status_code=404, detail="Appraisal record not found")

    ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    upload_url, file_key = build_upload_url(record, "appraisal-file")
    return {"upload_url": upload_url, "file_key": file_key}


@router.get("/{rm_tran_no}/files/{file_key:path}/download-url", response_model=DownloadUrlResponse)
def get_download_url(
    rm_tran_no: int,
    file_key: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_caller),
):
    record = get_appraisal_record(db, rm_tran_no)
    if record is None:
        raise HTTPException(status_code=404, detail="Appraisal record not found")

    download_url = build_download_url(file_key)
    return {"download_url": download_url}

