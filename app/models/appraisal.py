from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import relationship
from app.db.base import Base
from sqlalchemy import JSON


class PerformanceAppraisalModel(Base):
    __tablename__ = "performance_appraisals"

    id = Column(Integer, primary_key=True)
    employee_id = Column(BigInteger, nullable=False, unique=True, index=True)
    contract_sdate = Column(Date, nullable=False)
    bu_tagging = Column(String(255), nullable=False, index=True)

    third_month_due_date = Column(Date)
    third_month_notified_at = Column(DateTime(timezone=True))
    third_month_decision = Column(
        Enum("PROCEED_5TH", "NON_REGULARIZATION", "NO_APPRAISAL", name="third_month_decision")
    )
    third_month_appraisal_file_key = Column(String(1024))
    third_month_decided_at = Column(DateTime(timezone=True))
    third_month_decided_by = Column(Integer, ForeignKey("users.id"))

    fifth_month_due_date = Column(Date)
    fifth_month_notified_at = Column(DateTime(timezone=True))
    fifth_month_decision = Column(
        Enum(
            "REGULARIZATION",
            "NON_REGULARIZATION",
            "NO_APPRAISAL",
            "EXTENSION",
            name="fifth_month_decision",
        )
    )
    fifth_month_appraisal_file_key = Column(String(1024))
    fifth_month_decided_at = Column(DateTime(timezone=True))
    fifth_month_decided_by = Column(Integer, ForeignKey("users.id"))

    sixth_month_check_date = Column(Date)
    failsafe_triggered = Column(Boolean, default=False)
    failsafe_triggered_at = Column(DateTime(timezone=True))
    failsafe_reason = Column(
        Enum(
            "NO_3RD_MONTH_APPRAISAL",
            "NO_5TH_MONTH_DECISION",
            "EXTENSION_UNRESOLVED",
            name="failsafe_reason",
        )
    )

    appraisal_status = Column(
        Enum(
            "PENDING",
            "FOR_REGULARIZATION",
            "REGULARIZED",
            "NON_REGULARIZED",
            "NEEDS_REVIEW",
            "RESOLVED_MANUAL",
            name="appraisal_status",
        ),
        default="PENDING",
        nullable=False,
        index=True,
    )
    confirmed_at = Column(DateTime(timezone=True))

    resolution_reason = Column(
        Enum(
            "LEFT_COMPANY",
            "AWOL",
            "TRANSFERRED",
            "DATA_ERROR",
            "OTHER",
            name="resolution_reason",
        )
    )
    resolution_notes = Column(String(2000))
    resolution_resolved_by = Column(Integer, ForeignKey("users.id"))
    resolution_resolved_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    extension_records = relationship(
        "ExtensionRecordModel",
        back_populates="appraisal",
        order_by="ExtensionRecordModel.sequence",
        cascade="all, delete-orphan",
    )


class NotificationModel(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    recipient_type = Column(Enum("BU_GROUP", "ROLE", name="recipient_type"), nullable=False)
    recipient_value = Column(String(255), nullable=False)
    milestone = Column(String(255), nullable=False)
    employee_id = Column(BigInteger, nullable=False, index=True)
    message = Column(String(1000), nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExtensionRecordModel(Base):
    __tablename__ = "extension_records"

    id = Column(Integer, primary_key=True)
    appraisal_id = Column(Integer, ForeignKey("performance_appraisals.id"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)

    extension_until = Column(Date, nullable=False)
    granted_at = Column(DateTime(timezone=True), server_default=func.now())
    granted_by = Column(Integer, ForeignKey("users.id"))

    decision = Column(
        Enum("REGULARIZATION", "NON_REGULARIZATION", "EXTENSION", name="extension_record_decision")
    )
    appraisal_file_key = Column(String(1024))
    decided_at = Column(DateTime(timezone=True))
    decided_by = Column(Integer, ForeignKey("users.id"))

    appraisal = relationship("PerformanceAppraisalModel", back_populates="extension_records")


class ActivityLogModel(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True)
    employee_id = Column(BigInteger, nullable=False, index=True)

    action = Column(
        Enum(
            "THIRD_MONTH_DECISION",
            "FIFTH_MONTH_DECISION",
            "EXTENSION_DECISION",
            "UPLOAD_URL_ISSUED",
            name="activity_log_action",
        ),
        nullable=False,
    )
    status = Column(Enum("SUCCESS", "FAILURE", name="activity_log_status"), nullable=False)

    actor_type = Column(Enum("INTERNAL", "EXTERNAL", name="activity_log_actor_type"), nullable=False)
    actor_id = Column(String(255), nullable=False)
    bu_group = Column(String(255))

    detail = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())