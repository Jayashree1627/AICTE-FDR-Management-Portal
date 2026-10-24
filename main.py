from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .app.config import settings
from .app.database import engine, Base
from .app.routes import (
    auth_router,
    cases_router,
    institutions_router,
    overlaps_router,
    dashboard_router,
    alerts_router,
    reports_router
)

# Create tables automatically on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Centralized AICTE complaint monitoring, cross-bureau overlap detection & SLA management dashboard"
)

# Enable CORS for Vite frontend (localhost:5173, localhost:3000, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers under /api
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(cases_router, prefix=settings.API_PREFIX)
app.include_router(institutions_router, prefix=settings.API_PREFIX)
app.include_router(overlaps_router, prefix=settings.API_PREFIX)
app.include_router(dashboard_router, prefix=settings.API_PREFIX)
app.include_router(alerts_router, prefix=settings.API_PREFIX)
app.include_router(reports_router, prefix=settings.API_PREFIX)

@app.get("/")
def root():
    return {
        "status": "online",
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "api_prefix": settings.API_PREFIX
    }

@app.get("/health")
def health():
    return {"status": "healthy"}
