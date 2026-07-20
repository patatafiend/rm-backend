from contextlib import asynccontextmanager

from app.core.config import settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.api.v1.router import api_router
from app.db.session import SessionLocal
from app.services.appraisal import run_appraisal_cycle_job

scheduler = BackgroundScheduler()


def run_appraisal_cycle():
    db = SessionLocal()
    try:
        run_appraisal_cycle_job(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        run_appraisal_cycle,
        trigger=CronTrigger(hour=0, minute=0),  # runs once daily at 00:00 server time
        id="appraisal_cycle_job",
        replace_existing=True,
    )
    scheduler.start()

    yield

    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

origins = [settings.FRONTEND_URL]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def hello():
    return {"message": "App working!"}