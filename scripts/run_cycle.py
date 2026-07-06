# scripts/run_cycle.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
import app.models.user  # noqa: F401 — registers users table with SQLAlchemy metadata
import app.models.appraisal  # noqa: F401 — registers appraisal tables

from app.db.session import SessionLocal
from app.services.appraisal import run_appraisal_cycle_job

db = SessionLocal()
try:
    print("Running appraisal cycle job...")
    run_appraisal_cycle_job(db)
    print("Done.")
finally:
    db.close()