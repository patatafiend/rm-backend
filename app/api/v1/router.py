from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, roles, permissions, companies, clients

api_router = APIRouter()

api_router.include_router(auth.router,        prefix="/auth",        tags=["Auth"])
api_router.include_router(users.router,       prefix="/users",       tags=["Users"])
api_router.include_router(roles.router,       prefix="/roles",       tags=["Roles"])
api_router.include_router(permissions.router, prefix="/permissions",  tags=["Permissions"])
api_router.include_router(companies.router,   prefix="/companies",   tags=["Companies"])
api_router.include_router(clients.router,     prefix="/clients",     tags=["Clients"])