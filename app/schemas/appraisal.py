from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, model_validator


AppraisalStatus = Literal[
    "PENDING",
    "FOR_REGULARIZATION",
    "REGULARIZED",
    "NON_REGULARIZED",
    "NEEDS_REVIEW",
    "RESOLVED_MANUAL",
]

ThirdMonthDecision = Literal["PROCEED_5TH", "NON_REGULARIZATION", "NO_APPRAISAL"]
FifthMonthDecision = Literal["REGULARIZATION", "NON_REGULARIZATION", "EXTENSION", "NO_APPRAISAL"]
ExtensionDecision = Literal["REGULARIZATION", "NON_REGULARIZATION", "EXTENSION"]


class ExtensionRecordRead(BaseModel):
    id: int
    sequence: int
    extension_until: date | None = None
    granted_at: datetime | None = None
    decision: ExtensionDecision | None = None
    appraisal_file_key: str | None = None
    decided_at: datetime | None = None

    model_config = {"from_attributes": True}


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
    third_month_appraisal_file_key: str | None = None   # needed for drawer download link
    third_month_decided_at: datetime | None = None       # needed for history timeline
    third_month_notified_at: datetime | None = None

    fifth_month_due_date: date | None = None
    fifth_month_decision: FifthMonthDecision | None = None
    fifth_month_appraisal_file_key: str | None = None
    fifth_month_decided_at: datetime | None = None
    fifth_month_notified_at: datetime | None = None
    sixth_month_check_date: date | None = None

    extension_records: list[ExtensionRecordRead] = []

    appraisal_status: AppraisalStatus
    failsafe_reason: Literal[
        "NO_3RD_MONTH_APPRAISAL",
        "NO_5TH_MONTH_DECISION",
        "EXTENSION_UNRESOLVED",
    ] | None = None
    failsafe_triggered_at: datetime | None = None
    confirmed_at: datetime | None = None

    resolution_reason: str | None = None
    resolution_notes: str | None = None
    resolution_resolved_at: datetime | None = None

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
    appraisal_file_key: str | None = None
    extension_until: date | None = None


class ExtensionDecisionPayload(BaseModel):
    decision: ExtensionDecision
    appraisal_file_key: str | None = None
    extension_until: date | None = None

    @model_validator(mode="after")
    def validate_fields_for_decision(self) -> "ExtensionDecisionPayload":
        if self.decision == "EXTENSION" and self.extension_until is None:
            raise ValueError("extension_until is required when decision is EXTENSION")
        if self.decision != "EXTENSION" and not self.appraisal_file_key:
            raise ValueError("appraisal_file_key is required for a final decision")
        return self


class UploadUrlResponse(BaseModel):
    upload_url: str
    file_key: str


class DownloadUrlResponse(BaseModel):
    download_url: str