# scripts/debug_appraisal_cycle.py
# Run from the rm-backend repo root: python debug_appraisal_cycle.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.services.appraisal import fetch_all_employees, ELIGIBLE_STATUSES
from app.models.appraisal import PerformanceAppraisalModel

db = SessionLocal()
try:
    print("Fetching from external feeds...")
    employees = fetch_all_employees()
    print(f"  -> {len(employees)} employees fetched total (both feeds combined)")

    eligible = [
        e for e in employees
        if str(e.get("estatus", "")).strip().upper() in ELIGIBLE_STATUSES
    ]
    print(f"  -> {len(eligible)} eligible (estatus == PROBATIONARY)")

    if eligible:
        sample = eligible[0]
        print("  -> sample eligible employee:", {
            k: sample.get(k) for k in ("empidno", "estatus", "firstdatehired", "bu_grouping")
        })
    elif employees:
        sample = employees[0]
        print("  -> no PROBATIONARY employees. sample raw estatus values seen:",
              {e.get("estatus") for e in employees[:20]})

    print()
    print("Querying performance_appraisals table directly...")
    rows = db.query(PerformanceAppraisalModel).all()
    print(f"  -> {len(rows)} row(s) in performance_appraisals")
    for r in rows[:15]:
        print(
            f"     employee_id={r.employee_id} contract_sdate={r.contract_sdate} "
            f"third_month_notified_at={r.third_month_notified_at} "
            f"appraisal_status={r.appraisal_status}"
        )
finally:
    db.close()