"""
Reknew Orbit — Backend API

FastAPI with SQLite + TOTP authentication.
"""

import logging
from datetime import date
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import create_tables, SessionLocal
from app.api.employees import router as employees_router
from app.api.auth import router as auth_router
from app.models.employee import Employee
from app.services.auth_service import hash_password, generate_totp_secret

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def seed_admin():
    """Create the super admin account if it doesn't exist."""
    db = SessionLocal()
    try:
        admin = db.query(Employee).filter(
            Employee.work_email == "superadmin@reknew.ai"
        ).first()

        if not admin:
            admin = Employee(
                first_name="Super",
                last_name="Admin",
                work_email="superadmin@reknew.ai",
                phone="0000000000",
                workforce_type="Full-Time Employee",
                role="Admin",
                department="People",
                reporting_manager="Self",
                joining_date=date(2024, 1, 1),
                work_location="Onshore",
                password_hash=hash_password("test"),
                totp_secret=None,  # Admin uses simple login for now
                is_first_login=False,
                is_active=True,
                setup_code=None,
            )
            db.add(admin)
            db.commit()
            logger.info("Super admin account seeded: superadmin@reknew.ai / test")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    create_tables()
    seed_admin()
    logger.info("Database tables created and admin seeded")
    yield


app = FastAPI(
    title="Reknew Orbit API",
    description="Employee Management System with TOTP Authentication",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(employees_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"app": "Reknew Orbit API", "version": "2.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "auth": "TOTP (Microsoft Authenticator)"}
