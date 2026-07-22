import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.employee import Employee
from app.models.leave_attendance import LeaveBalance, LeaveRequest, LeaveType
from app.models.operations import CompanyHoliday
from app.models.organization import Department, Designation
from app.schemas.leave import LeaveAssessmentInput, LeaveRequestInput
from app.services.leave_service import (
    LeaveServiceError,
    assess_my_leave_request,
    get_my_leave_context,
    get_my_leave_request_by_id,
    submit_my_leave_request,
)


class LeaveServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(
            self.engine,
            tables=[
                Department.__table__,
                Designation.__table__,
                Employee.__table__,
                LeaveType.__table__,
                LeaveBalance.__table__,
                LeaveRequest.__table__,
                CompanyHoliday.__table__,
            ],
        )
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = self.Session()
        self.today = date(2026, 7, 20)
        self.employee = Employee(
            id="employee-1",
            first_name="Asha",
            last_name="Rao",
            work_email="asha@example.com",
            phone="1000000000",
            workforce_type="full_time",
            role="employee",
            employment_status="active",
            is_active=True,
            gender="female",
            reporting_manager="Mina Shah",
            joining_date=date(2025, 1, 1),
            date_of_joining=date(2025, 1, 1),
            work_location="US",
        )
        self.other_employee = Employee(
            id="employee-2",
            first_name="Other",
            last_name="Person",
            work_email="other@example.com",
            phone="2000000000",
            workforce_type="full_time",
            role="employee",
            employment_status="active",
            is_active=True,
            gender="male",
            reporting_manager="Mina Shah",
            joining_date=date(2025, 1, 1),
            work_location="US",
        )
        self.casual = LeaveType(
            id="leave-cl",
            name="Casual Leave",
            code="CL",
            default_days_per_year=12,
            is_paid=True,
            is_carry_forward=True,
            max_carry_forward_days=5,
            allow_future_dates=True,
            is_active=True,
            sort_order=1,
        )
        self.bereavement = LeaveType(
            id="leave-bl",
            name="Bereavement Leave",
            code="BL",
            default_days_per_year=5,
            is_paid=True,
            is_carry_forward=False,
            max_carry_forward_days=0,
            allow_future_dates=True,
            past_date_limit_days=30,
            is_active=True,
            sort_order=2,
        )
        self.db.add_all([self.employee, self.other_employee, self.casual, self.bereavement])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _assessment(self, **updates):
        values = {
            "leave_type_id": self.casual.id,
            "start_date": self.today + timedelta(days=7),
            "end_date": self.today + timedelta(days=9),
        }
        values.update(updates)
        return assess_my_leave_request(
            self.db,
            self.employee,
            LeaveAssessmentInput(**values),
            as_of=datetime(2026, 7, 20, 12, 0, 0),
        )

    def test_context_read_does_not_create_missing_balances_or_commit_state(self):
        self.assertEqual(self.db.query(LeaveBalance).count(), 0)

        context = get_my_leave_context(
            self.db, self.employee, as_of=datetime(2026, 7, 20, 12, 0, 0)
        )

        self.assertEqual(self.db.query(LeaveBalance).count(), 0)
        self.assertFalse(self.db.new)
        self.assertFalse(self.db.dirty)
        casual = next(item for item in context.balances if item.code == "CL")
        self.assertEqual(casual.total, 12)
        self.assertEqual(casual.effective_available, 12)
        self.assertFalse(casual.initialized)

    def test_eligibility_read_does_not_change_any_table(self):
        counts_before = {
            "balances": self.db.query(LeaveBalance).count(),
            "requests": self.db.query(LeaveRequest).count(),
            "holidays": self.db.query(CompanyHoliday).count(),
        }

        result = self._assessment()

        self.assertTrue(result.eligible)
        self.assertEqual(result.payable_working_days, 3)
        self.assertEqual(result.effective_balance_before, 12)
        self.assertEqual(result.effective_balance_after, 9)
        self.assertEqual(counts_before, {
            "balances": self.db.query(LeaveBalance).count(),
            "requests": self.db.query(LeaveRequest).count(),
            "holidays": self.db.query(CompanyHoliday).count(),
        })
        self.assertFalse(self.db.new)
        self.assertFalse(self.db.dirty)

    def test_assessment_reports_excluded_weekend_and_holiday(self):
        self.db.add(CompanyHoliday(
            id="holiday-1",
            name="Company Day",
            holiday_date=date(2026, 7, 27),
            holiday_type="company",
            regions="US",
            is_active=True,
        ))
        self.db.commit()

        result = self._assessment(
            start_date=date(2026, 7, 25), end_date=date(2026, 7, 28)
        )

        self.assertEqual([item.date for item in result.excluded_weekends], [
            date(2026, 7, 25), date(2026, 7, 26)
        ])
        self.assertEqual([item.date for item in result.excluded_holidays], [date(2026, 7, 27)])
        self.assertEqual(result.payable_working_days, 1)

    def test_cross_year_request_is_rejected_with_stable_code(self):
        result = self._assessment(
            start_date=date(2026, 12, 31), end_date=date(2027, 1, 2)
        )

        self.assertFalse(result.eligible)
        self.assertIn("CROSS_YEAR_LEAVE_NOT_SUPPORTED", {
            item.code for item in result.blocking_reasons
        })

    def test_past_date_policy_conflict_preserves_production_rule(self):
        """BL advertises a past window, but general production policy still blocks past dates."""
        result = self._assessment(
            leave_type_id=self.bereavement.id,
            start_date=date(2026, 7, 15),
            end_date=date(2026, 7, 15),
        )

        self.assertFalse(result.eligible)
        self.assertIn("PAST_DATE_NOT_ALLOWED", {item.code for item in result.blocking_reasons})
        self.assertEqual(result.policy.past_date_limit_days, 30)
        self.assertFalse(result.policy.past_dates_currently_allowed)

    def test_owner_scoped_lookup_hides_other_employee_request(self):
        other_request = LeaveRequest(
            id="other-request",
            employee_id=self.other_employee.id,
            leave_type_id=self.casual.id,
            start_date=date(2026, 8, 3),
            end_date=date(2026, 8, 3),
            total_days=1,
            reason="Private",
            status="pending",
        )
        self.db.add(other_request)
        self.db.commit()

        for request_id in (other_request.id, "does-not-exist"):
            with self.assertRaises(LeaveServiceError) as raised:
                get_my_leave_request_by_id(self.db, self.employee, request_id)
            self.assertEqual(raised.exception.code, "LEAVE_REQUEST_NOT_FOUND")
            self.assertEqual(raised.exception.status_code, 404)
            self.assertEqual(raised.exception.message, "Leave request not found.")

    @patch("app.services.leave_service.log_audit")
    def test_submission_returns_explicit_typed_result_and_provisions_balance(self, audit):
        payload = LeaveRequestInput(
            leave_type_id=self.casual.id,
            start_date=date(2026, 8, 3),
            end_date=date(2026, 8, 5),
            reason="Family event",
            action="submit",
        )
        with patch("app.services.leave_service.datetime") as clock:
            clock.utcnow.return_value = datetime(2026, 7, 20, 14, 0, 0)
            result = submit_my_leave_request(
                self.db, self.employee, payload, correlation_id="corr-123"
            )

        self.assertEqual(result.request_id, result.request.id)
        self.assertEqual(result.authoritative_initial_status, "pending")
        self.assertEqual(result.request.status, "pending")
        self.assertEqual(result.pending_approval_owner, "Mina Shah")
        self.assertEqual(result.correlation_id, "corr-123")
        self.assertEqual(self.db.query(LeaveRequest).count(), 1)
        self.assertEqual(self.db.query(LeaveBalance).count(), 1)
        audit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
