from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, roles, permissions, companies, clients, employee_requirements, analytics, appraisals, notifications

api_router = APIRouter()

api_router.include_router(auth.router,        prefix="/auth",        tags=["Auth"])
api_router.include_router(users.router,       prefix="/users",       tags=["Users"])
api_router.include_router(roles.router,       prefix="/roles",       tags=["Roles"])
api_router.include_router(permissions.router, prefix="/permissions",  tags=["Permissions"])
api_router.include_router(companies.router,   prefix="/companies",   tags=["Companies"])
api_router.include_router(clients.router,     prefix="/clients",     tags=["Clients"])
api_router.include_router(employee_requirements.router, tags=["Employee Requirements"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(appraisals.router, prefix="/appraisals", tags=["Performance Appraisals"])
api_router.include_router(notifications.router, tags=["Notifications"])