from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import user as _user_models  # noqa: F401
from app.models.appraisal import NotificationModel, PerformanceAppraisalModel
from app.services import appraisal as appraisal_service


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def test_add_months_uses_calendar_months():
    assert appraisal_service.add_months(date(2026, 2, 17), 3) == date(2026, 5, 17)
    assert appraisal_service.add_months(date(2026, 2, 17), 5) == date(2026, 7, 17)
    assert appraisal_service.add_months(date(2026, 2, 17), 6) == date(2026, 8, 17)


def test_compute_calendar_months_since_counts_full_months():
    assert appraisal_service.compute_calendar_months_since(date(2026, 2, 17), date(2026, 5, 17)) == 3
    assert appraisal_service.compute_calendar_months_since(date(2026, 2, 17), date(2026, 7, 17)) == 5
    assert appraisal_service.compute_calendar_months_since(date(2026, 2, 17), date(2026, 8, 17)) == 6


def test_get_or_create_appraisal_record_reuses_existing_row():
    db_session = make_session()
    employee = {"rm_tran_no": 18757, "erms_id": 58909998, "contract_sdate": "2026-02-17", "bu_tagging": "Recruitment - Delivery"}

    try:
        first = appraisal_service.get_or_create_appraisal_record(db_session, employee)
        second = appraisal_service.get_or_create_appraisal_record(db_session, employee)

        assert first.id == second.id
        assert db_session.query(PerformanceAppraisalModel).count() == 1
    finally:
        db_session.close()


def test_run_appraisal_cycle_job_triggers_failsafe_and_notifications():
    db_session = make_session()
    original_fetch_all_employees = appraisal_service.fetch_all_employees
    original_compute_calendar_months_since = appraisal_service.compute_calendar_months_since

    try:
        appraisal_service.fetch_all_employees = lambda: [
            {
                "rm_tran_no": 18757,
                "erms_id": 58909998,
                "contract_sdate": "2026-02-17",
                "bu_tagging": "Recruitment - Delivery",
                "emp_status": "PROBATIONARY",
                "rm_first_name": "EDCYL",
                "rm_middle_name": "A",
                "rm_lastname": "AYO",
                "rm_other_name": "",
                "hr_company": "FAST DELI SERV, INC.",
                "hr_client": "PHILSEVEN CORPORATION LAPAZ MARKET ILOILO",
                "rm_pos_applied": "SALES AREA MAINTENANCE",
            }
        ]
        appraisal_service.compute_calendar_months_since = lambda *args, **_kwargs: 6

        appraisal_service.run_appraisal_cycle_job(db_session)

        record = db_session.query(PerformanceAppraisalModel).one()
        assert record.appraisal_status == "FOR_REGULARIZATION"
        assert record.failsafe_triggered is True
        assert record.failsafe_reason == "NO_3RD_MONTH_APPRAISAL"
        assert record.third_month_notified_at is not None
        assert record.fifth_month_notified_at is not None
        assert record.sixth_month_check_date is not None

        notifications = db_session.query(NotificationModel).all()
        assert len(notifications) == 6
        assert {notification.recipient_type for notification in notifications} == {"BU_GROUP", "ROLE"}
    finally:
        appraisal_service.fetch_all_employees = original_fetch_all_employees
        appraisal_service.compute_calendar_months_since = original_compute_calendar_months_since
        db_session.close()