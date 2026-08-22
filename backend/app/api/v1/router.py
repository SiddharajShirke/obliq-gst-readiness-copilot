from fastapi import APIRouter

from app.api.v1 import (
    alerts,
    applications,
    audit,
    clients,
    compliance,
    demo,
    documents,
    firms,
    health,
    rag,
    users,
    whatsapp,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(demo.router)
api_router.include_router(users.router)
api_router.include_router(firms.router)
api_router.include_router(clients.router)
api_router.include_router(applications.router)
api_router.include_router(documents.router)
api_router.include_router(whatsapp.router)
api_router.include_router(rag.router)
api_router.include_router(compliance.router)
api_router.include_router(alerts.router)
api_router.include_router(audit.router)
