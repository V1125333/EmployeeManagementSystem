import unittest
from datetime import date
from types import SimpleNamespace

from app.services.work_calendar_service import (
    employee_region,
    employee_working_weekdays,
    is_employee_working_day,
    payable_leave_day_count,
    payable_leave_dates,
)


class EmptyQuery:
    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return []


class EmptyDb:
    def query(self, *args, **kwargs):
        return EmptyQuery()


class WorkCalendarServiceTests(unittest.TestCase):
    def test_structured_work_country_takes_precedence_over_arrangement(self):
        employee = SimpleNamespace(
            work_city="Hartford",
            work_state="CT",
            work_country="United States",
            work_location="Remote",
            location="Onshore",
        )

        self.assertEqual(employee_region(employee), "US")

    def test_standard_employee_leave_excludes_weekends(self):
        employee = SimpleNamespace(work_location="US", work_schedule=None)
        leave_type = SimpleNamespace(code="CL")

        days = payable_leave_dates(EmptyDb(), employee, leave_type, date(2026, 6, 25), date(2026, 7, 10))

        self.assertEqual([day.isoformat() for day in days], [
            "2026-06-25",
            "2026-06-26",
            "2026-06-29",
            "2026-06-30",
            "2026-07-01",
            "2026-07-02",
            "2026-07-03",
            "2026-07-06",
            "2026-07-07",
            "2026-07-08",
            "2026-07-09",
            "2026-07-10",
        ])
        self.assertEqual(payable_leave_day_count(EmptyDb(), employee, leave_type, date(2026, 6, 25), date(2026, 7, 10)), 12.0)

    def test_custom_schedule_can_include_saturday(self):
        employee = SimpleNamespace(working_days="mon,tue,wed,thu,fri,sat", work_location="US")

        self.assertEqual(employee_working_weekdays(employee), {0, 1, 2, 3, 4, 5})
        self.assertTrue(is_employee_working_day(employee, date(2026, 6, 27)))
        self.assertFalse(is_employee_working_day(employee, date(2026, 6, 28)))


if __name__ == "__main__":
    unittest.main()
