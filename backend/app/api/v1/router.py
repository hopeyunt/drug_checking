from fastapi import APIRouter
from app.api.v1 import auth, users, interactions, billing, admin, patients

api_router = APIRouter()
api_router.include_router(auth.router,         prefix="/auth",         tags=["Auth"])
api_router.include_router(users.router,        prefix="/users",        tags=["Users"])
api_router.include_router(interactions.router, prefix="/interactions", tags=["Interactions"])
api_router.include_router(billing.router,      prefix="/billing",      tags=["Billing"])
api_router.include_router(admin.router,        prefix="/admin",        tags=["Admin"])
api_router.include_router(patients.router,     prefix="/patients",     tags=["Patients"])
