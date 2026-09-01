from __future__ import annotations

from app.services.orbit_agent.orbit_capabilities import (
    ORBIT_CAPABILITIES,
    OrbitExecutor,
    OrbitIntent,
)


def test_orbit_capabilities_enable_current_local_utilities():
    assert ORBIT_CAPABILITIES[OrbitIntent.GREETING].enabled is True
    assert ORBIT_CAPABILITIES[OrbitIntent.GREETING].executor is OrbitExecutor.LOCAL
    assert ORBIT_CAPABILITIES[OrbitIntent.ACKNOWLEDGEMENT].enabled is True
    assert ORBIT_CAPABILITIES[OrbitIntent.ACKNOWLEDGEMENT].executor is OrbitExecutor.LOCAL
    assert ORBIT_CAPABILITIES[OrbitIntent.UTILITY_DATE].enabled is True
    assert ORBIT_CAPABILITIES[OrbitIntent.UTILITY_DATE].executor is OrbitExecutor.LOCAL
    assert ORBIT_CAPABILITIES[OrbitIntent.UTILITY_TIME].enabled is True
    assert ORBIT_CAPABILITIES[OrbitIntent.UTILITY_TIME].executor is OrbitExecutor.LOCAL
    assert ORBIT_CAPABILITIES[OrbitIntent.ORBIT_IDENTITY].enabled is True
    assert ORBIT_CAPABILITIES[OrbitIntent.ORBIT_IDENTITY].executor is OrbitExecutor.LOCAL
    assert ORBIT_CAPABILITIES[OrbitIntent.EMS_LEAVE].enabled is True
    assert ORBIT_CAPABILITIES[OrbitIntent.EMS_LEAVE].executor is OrbitExecutor.EMS_TOOL
    assert ORBIT_CAPABILITIES[OrbitIntent.EMS_ATTENDANCE].enabled is True
    assert ORBIT_CAPABILITIES[OrbitIntent.EMS_ATTENDANCE].executor is OrbitExecutor.EMS_TOOL
    assert ORBIT_CAPABILITIES[OrbitIntent.EMS_EMPLOYEE].enabled is True
    assert ORBIT_CAPABILITIES[OrbitIntent.EMS_EMPLOYEE].executor is OrbitExecutor.EMS_TOOL
    assert ORBIT_CAPABILITIES[OrbitIntent.EMS_TIMESHEET].enabled is True
    assert ORBIT_CAPABILITIES[OrbitIntent.EMS_TIMESHEET].executor is OrbitExecutor.EMS_TOOL


def test_orbit_capabilities_keep_other_ems_placeholders_disabled():
    for intent in (
        OrbitIntent.EMS_ALLOCATION,
    ):
        capability = ORBIT_CAPABILITIES[intent]
        assert capability.enabled is False
        assert capability.executor is OrbitExecutor.EMS_TOOL
        assert capability.unavailable_message is not None
