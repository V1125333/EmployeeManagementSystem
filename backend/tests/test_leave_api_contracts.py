import unittest
from datetime import date, timedelta
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.leaves import router
from app.core.database import Base, get_db
from app.models.employee import Employee
from app.models.leave_attendance import LeaveBalance, LeaveRequest, LeaveType
from app.models.operations import CompanyHoliday
from app.models.organization import Department, Designation


class LeaveApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(
            cls.engine,
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
        cls.Session = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        def override_db():
            db = cls.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.engine.dispose()

    def setUp(self):
        db = self.Session()
        for model in (LeaveRequest, LeaveBalance, CompanyHoliday, LeaveType, Employee):
            db.query(model).delete()
        self.employee = Employee(
            id="api-employee-1",
            first_name="Asha",
            last_name="Rao",
            work_email="api-asha@example.com",
            phone="3000000000",
            workforce_type="full_time",
            role="employee",
            employment_status="active",
            is_active=True,
            gender="female",
            reporting_manager="Mina Shah",
            joining_date=date(2025, 1, 1),
            work_location="US",
        )
        self.other = Employee(
            id="api-employee-2",
            first_name="Other",
            last_name="Person",
            work_email="api-other@example.com",
            phone="4000000000",
            workforce_type="full_time",
            role="employee",
            employment_status="active",
            is_active=True,
            gender="male",
            reporting_manager="Mina Shah",
            joining_date=date(2025, 1, 1),
            work_location="US",
        )
        self.leave_type = LeaveType(
            id="api-leave-cl",
            name="Casual Leave",
            code="CL",
            default_days_per_year=12,
            is_paid=True,
            is_carry_forward=False,
            max_carry_forward_days=0,
            allow_future_dates=True,
            is_active=True,
            sort_order=1,
        )
        self.manager = Employee(
            id="api-manager-1",
            first_name="Mina",
            last_name="Shah",
            work_email="api-mina@example.com",
            phone="5000000000",
            workforce_type="full_time",
            role="manager",
            employment_status="active",
            is_active=True,
            reporting_manager="",
            joining_date=date(2024, 1, 1),
            work_location="US",
        )
        db.add_all([self.employee, self.other, self.manager, self.leave_type])
        db.commit()
        self.employee_id = self.employee.id
        self.employee_email = self.employee.work_email
        self.other_id = self.other.id
        self.leave_type_id = self.leave_type.id
        self.manager_id = self.manager.id
        self.manager_email = self.manager.work_email
        db.close()
        self.headers = {
            "x-user-id": self.employee_id,
            "x-user-email": self.employee_email,
        }

    def _counts(self):
        db = self.Session()
        try:
            return db.query(LeaveBalance).count(), db.query(LeaveRequest).count()
        finally:
            db.close()

    def test_typed_context_is_read_only_and_reports_uninitialized_balance(self):
        before = self._counts()
        response = self.client.get("/api/v1/leaves/me/context", headers=self.headers)
        after = self._counts()

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("as_of", payload)
        self.assertFalse(payload["balances"][0]["initialized"])
        self.assertEqual(payload["balances"][0]["effective_available"], 12.0)
        self.assertEqual(before, after)

    def test_legacy_summary_shape_remains_compatible_and_read_only(self):
        before = self._counts()
        response = self.client.get("/api/v1/leaves/me/summary", headers=self.headers)
        after = self._counts()

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertNotIn("as_of", payload)
        self.assertNotIn("initialized", payload["balances"][0])
        self.assertEqual(set(payload["balances"][0]["date_policy"]), {
            "allow_future_dates", "past_date_limit_days", "future_date_warning"
        })
        self.assertEqual(before, after)

    def test_assessment_contract_is_typed_read_only_and_rejects_unknown_fields(self):
        start = date.today() + timedelta(days=7)
        body = {
            "leave_type_id": self.leave_type_id,
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=2)).isoformat(),
        }
        before = self._counts()
        response = self.client.post("/api/v1/leaves/me/assess", headers=self.headers, json=body)
        after = self._counts()

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("eligible", payload)
        self.assertIn("payable_working_days", payload)
        self.assertIn("effective_balance_before", payload)
        self.assertIn("excluded_weekends", payload)
        self.assertIn("excluded_holidays", payload)
        self.assertIn("blocking_reasons", payload)
        self.assertIn("policy", payload)
        self.assertEqual(before, after)

        body["employee_id"] = self.other_id
        rejected = self.client.post("/api/v1/leaves/me/assess", headers=self.headers, json=body)
        self.assertEqual(rejected.status_code, 422)

    def test_owner_scoped_status_has_same_privacy_safe_response(self):
        db = self.Session()
        db.add(LeaveRequest(
            id="private-request",
            employee_id=self.other_id,
            leave_type_id=self.leave_type_id,
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=10),
            total_days=1,
            reason="Private",
            status="pending",
        ))
        db.commit()
        db.close()

        responses = [
            self.client.get(
                f"/api/v1/leaves/me/requests/{request_id}/status", headers=self.headers
            )
            for request_id in ("private-request", "missing-request")
        ]
        self.assertEqual([item.status_code for item in responses], [404, 404])
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assertEqual(responses[0].json()["detail"]["code"], "LEAVE_REQUEST_NOT_FOUND")

    @patch("app.services.leave_service.log_audit")
    def test_submission_returns_created_id_and_owner_scoped_status(self, _audit):
        start = date.today() + timedelta(days=14)
        response = self.client.post(
            "/api/v1/leaves/me/submissions",
            headers={**self.headers, "x-correlation-id": "contract-correlation"},
            json={
                "leave_type_id": self.leave_type_id,
                "start_date": start.isoformat(),
                "end_date": (start + timedelta(days=2)).isoformat(),
                "reason": "Family event"
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertEqual(payload["request_id"], payload["request"]["id"])
        self.assertEqual(payload["authoritative_initial_status"], "pending")
        self.assertEqual(payload["request"]["status"], "pending")
        self.assertEqual(payload["pending_approval_owner"], "Mina Shah")
        self.assertEqual(payload["correlation_id"], "contract-correlation")

        status = self.client.get(
            f"/api/v1/leaves/me/requests/{payload['request_id']}/status",
            headers=self.headers,
        )
        self.assertEqual(status.status_code, 200, status.text)
        self.assertEqual(status.json()["request_id"], payload["request_id"])
        self.assertEqual(status.json()["status"], "pending")

        rejected_extra_field = self.client.post(
            "/api/v1/leaves/me/submissions",
            headers=self.headers,
            json={
                "leave_type_id": self.leave_type_id,
                "start_date": start.isoformat(),
                "end_date": start.isoformat(),
                "reason": "Should not be accepted",
                "action": "draft",
            },
        )
        self.assertEqual(rejected_extra_field.status_code, 422)

    @patch("app.api.leaves.log_audit")
    def test_existing_manager_approval_flow_still_consumes_balance(self, _audit):
        db = self.Session()
        db.add(LeaveRequest(
            id="approval-request",
            employee_id=self.employee_id,
            leave_type_id=self.leave_type_id,
            start_date=date.today() + timedelta(days=20),
            end_date=date.today() + timedelta(days=20),
            total_days=1,
            reason="Family event",
            status="pending",
        ))
        db.commit()
        db.close()

        response = self.client.post(
            "/api/v1/leaves/approvals/approval-request/decision",
            headers={"x-user-id": self.manager_id, "x-user-email": self.manager_email},
            json={"decision": "approve", "reviewer_notes": "Approved"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        db = self.Session()
        try:
            request = db.query(LeaveRequest).filter(LeaveRequest.id == "approval-request").one()
            balance = db.query(LeaveBalance).filter(
                LeaveBalance.employee_id == self.employee_id,
                LeaveBalance.leave_type_id == self.leave_type_id,
            ).one()
            self.assertEqual(request.status, "approved")
            self.assertEqual(float(balance.used_days), 1.0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
