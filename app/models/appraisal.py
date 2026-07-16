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


class PerformanceAppraisalModel(Base):
    __tablename__ = "performance_appraisals"

    id = Column(Integer, primary_key=True)
    rm_tran_no = Column(Integer, nullable=False, unique=True, index=True)
    erms_id = Column(BigInteger, nullable=False)
    contract_sdate = Column(Date, nullable=False)
    bu_tagging = Column(String(255), nullable=False, index=True)

    third_month_due_date = Column(Date)
    third_month_notified_at = Column(DateTime(timezone=True))
    third_month_decision = Column(
        Enum("PROCEED_5TH", "NON_REGULARIZATION", name="third_month_decision")
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
    rm_tran_no = Column(Integer, nullable=False, index=True)
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