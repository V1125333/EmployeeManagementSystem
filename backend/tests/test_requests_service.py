import unittest
from datetime import date
from types import SimpleNamespace

from fastapi import HTTPException

from app.services.requests_service import (
    REQUEST_POLICIES,
    _is_direct_report,
    _policy_bounds,
    _validate_date_against_policy,
)


class RequestPolicyTests(unittest.TestCase):
    def test_wfh_policy_rejects_past_dates(self):
        policy = REQUEST_POLICIES["wfh"]

        with self.assertRaises(HTTPException) as context:
            _validate_date_against_policy(policy, None, date(2026, 6, 25), "From Date")

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("Work From Home", context.exception.detail)

    def test_expense_policy_allows_configured_pre_joining_window(self):
        policy = REQUEST_POLICIES["expense"]
        employee = SimpleNamespace(joining_date=date(2026, 6, 20))
        min_date, max_date = _policy_bounds(policy, employee, today=date(2026, 6, 26))

        self.assertEqual(min_date, date(2026, 6, 6))
        self.assertEqual(max_date, date(2026, 6, 26))

    def test_reporting_manager_identity_is_separate_from_project_allocation(self):
        manager = SimpleNamespace(id="mgr-1", first_name="David", last_name="Park", work_email="david.park@reknew.ai")
        employee = SimpleNamespace(id="emp-1", manager_id="mgr-1", reporting_manager="")

        self.assertTrue(_is_direct_report(manager, employee))

    def test_legacy_reporting_manager_name_still_works(self):
        manager = SimpleNamespace(id="mgr-1", first_name="David", last_name="Park", work_email="david.park@reknew.ai")
        employee = SimpleNamespace(id="emp-1", manager_id=None, reporting_manager="David Park")

        self.assertTrue(_is_direct_report(manager, employee))


if __name__ == "__main__":
    unittest.main()
