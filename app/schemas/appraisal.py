from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


AppraisalStatus = Literal[
    "PENDING",
    "FOR_REGULARIZATION",
    "REGULARIZED",
    "NON_REGULARIZED",
    "NEEDS_REVIEW",
    "RESOLVED_MANUAL",
]

ThirdMonthDecision = Literal["PROCEED_5TH", "NON_REGULARIZATION"]
FifthMonthDecision = Literal["REGULARIZATION", "NON_REGULARIZATION", "EXTENSION"]
ExtensionDecision = Literal["REGULARIZATION", "NON_REGULARIZATION"]


class AppraisalRecordRead(BaseModel):
    rm_tran_no: int
    erms_id: int
    employee_name: str | None = None
    hr_company: str | None = None
    hr_client: str | None = None
    bu_tagging: str
    rm_pos_applied: str | None = None
    contract_sdate: date
    third_month_due_date: date | None = None
    third_month_decision: ThirdMonthDecision | None = None
    third_month_notified_at: datetime | None = None
    fifth_month_due_date: date | None = None
    fifth_month_decision: FifthMonthDecision | None = None
    fifth_month_notified_at: datetime | None = None
    extension_until: date | None = None
    extension_final_decision: ExtensionDecision | None = None
    appraisal_status: AppraisalStatus
    failsafe_reason: Literal[
        "NO_3RD_MONTH_APPRAISAL",
        "NO_5TH_MONTH_DECISION",
        "EXTENSION_UNRESOLVED",
    ] | None = None
    failsafe_triggered_at: datetime | None = None

    model_config = {"from_attributes": True}


class AppraisalListResponse(BaseModel):
    status: Literal["success"] = "success"
    total: int
    data: list[AppraisalRecordRead]


class ThirdMonthSubmissionPayload(BaseModel):
    decision: ThirdMonthDecision
    appraisal_file_key: str


class FifthMonthSubmissionPayload(BaseModel):
    decision: FifthMonthDecision
    appraisal_file_key: str
    extension_until: date | None = None


class ExtensionDecisionPayload(BaseModel):
    decision: ExtensionDecision


class UploadUrlResponse(BaseModel):
    upload_url: str
    file_key: str


class DownloadUrlResponse(BaseModel):
    download_url: str