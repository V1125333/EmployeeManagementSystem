from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.employee import Employee
from app.models.settings import OrganizationSecurityPolicy, UserSettings
from app.services.mfa_policy_service import is_mfa_required, update_user_mfa_preference


def employee() -> Employee:
    return Employee(
        id="employee-mfa",
        first_name="Mfa",
        last_name="User",
        work_email="mfa.user@example.com",
        phone="5550001111",
        workforce_type="full_time",
        role="employee",
        employment_status="active",
        reporting_manager="",
        joining_date=date(2025, 1, 1),
        date_of_joining=date(2025, 1, 1),
        work_location="US",
        is_active=True,
        is_first_login=False,
        totp_secret="JBSWY3DPEHPK3PXP",
        mfa_enabled=True,
    )


def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_user_can_opt_out_without_deleting_authenticator_secret():
    Session = session_factory()
    with Session() as db:
        user = employee()
        db.add_all([
            user,
            OrganizationSecurityPolicy(id="organization", mfa_enabled=True, allow_user_mfa_opt_out=True),
            UserSettings(user_id=user.id, mfa_enabled=True),
        ])
        db.commit()

        assert is_mfa_required(db, user) is True
        update_user_mfa_preference(db, user, False)
        db.commit()

        assert is_mfa_required(db, user) is False
        assert user.totp_secret == "JBSWY3DPEHPK3PXP"


def test_global_switch_bypasses_mfa_for_all_users():
    Session = session_factory()
    with Session() as db:
        user = employee()
        policy = OrganizationSecurityPolicy(id="organization", mfa_enabled=False, allow_user_mfa_opt_out=True)
        db.add_all([user, policy, UserSettings(user_id=user.id, mfa_enabled=True)])
        db.commit()

        assert is_mfa_required(db, user) is False


def test_disallowing_opt_out_overrides_a_users_disabled_preference():
    Session = session_factory()
    with Session() as db:
        user = employee()
        db.add_all([
            user,
            OrganizationSecurityPolicy(id="organization", mfa_enabled=True, allow_user_mfa_opt_out=False),
            UserSettings(user_id=user.id, mfa_enabled=False),
        ])
        db.commit()

        assert is_mfa_required(db, user) is True
