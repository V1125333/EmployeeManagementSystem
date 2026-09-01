from datetime import date, time

import pytest
from fastapi import HTTPException

from app.api import timesheets


def test_holiday_aware_weekly_target_excludes_non_working_days():
    monday = date(2026, 8, 10)
    result = timesheets.serialize_week(
        monday,
        [],
        workforce_type="full_time",
        requested_time_zone="America/New_York",
        non_working_dates={date(2026, 8, 12), date(2026, 8, 15), date(2026, 8, 16)},
    )

    assert result.weekly_limit_hours == 32
    assert result.non_working_days == [date(2026, 8, 12), date(2026, 8, 15), date(2026, 8, 16)]


def test_partial_day_leave_allows_complementary_project_hours_only():
    work_date = date(2026, 8, 10)
    four_hours = timesheets.TimesheetEntryPayload(
        work_date=work_date,
        entry_code="POC",
        project_name="Internal",
        start_time=time(9),
        end_time=time(13),
    )
    timesheets.assert_no_leave_conflicts([four_hours], {work_date: 4.0})

    five_hours = four_hours.model_copy(update={"end_time": time(14)})
    with pytest.raises(HTTPException, match="Work and leave exceed 8 hours"):
        timesheets.assert_no_leave_conflicts([five_hours], {work_date: 4.0})
