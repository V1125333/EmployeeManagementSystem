from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType


class OrbitIntent(str, Enum):
    GREETING = "greeting"
    ACKNOWLEDGEMENT = "acknowledgement"
    UTILITY_DATE = "utility_date"
    UTILITY_TIME = "utility_time"
    ORBIT_IDENTITY = "orbit_identity"
    DRAFTING = "drafting"
    GENERAL_REASONING = "general_reasoning"
    CONTEXT_FOLLOWUP = "context_followup"
    EMS_LEAVE = "ems_leave"
    EMS_ATTENDANCE = "ems_attendance"
    EMS_TIMESHEET = "ems_timesheet"
    EMS_ALLOCATION = "ems_allocation"
    EMS_EMPLOYEE = "ems_employee"
    UNKNOWN = "unknown"


class OrbitExecutor(str, Enum):
    LOCAL = "local"
    HERMES = "hermes"
    EMS_TOOL = "ems_tool"


@dataclass(frozen=True)
class OrbitCapability:
    intent: OrbitIntent
    enabled: bool
    executor: OrbitExecutor
    unavailable_message: str | None = None


ORBIT_CAPABILITIES = MappingProxyType(
    {
        OrbitIntent.GREETING: OrbitCapability(
            intent=OrbitIntent.GREETING,
            enabled=True,
            executor=OrbitExecutor.LOCAL,
        ),
        OrbitIntent.ACKNOWLEDGEMENT: OrbitCapability(
            intent=OrbitIntent.ACKNOWLEDGEMENT,
            enabled=True,
            executor=OrbitExecutor.LOCAL,
        ),
        OrbitIntent.UTILITY_DATE: OrbitCapability(
            intent=OrbitIntent.UTILITY_DATE,
            enabled=True,
            executor=OrbitExecutor.LOCAL,
        ),
        OrbitIntent.UTILITY_TIME: OrbitCapability(
            intent=OrbitIntent.UTILITY_TIME,
            enabled=True,
            executor=OrbitExecutor.LOCAL,
        ),
        OrbitIntent.ORBIT_IDENTITY: OrbitCapability(
            intent=OrbitIntent.ORBIT_IDENTITY,
            enabled=True,
            executor=OrbitExecutor.LOCAL,
        ),
        OrbitIntent.EMS_LEAVE: OrbitCapability(
            intent=OrbitIntent.EMS_LEAVE,
            enabled=True,
            executor=OrbitExecutor.EMS_TOOL,
            unavailable_message=(
                "I understand you're asking about leave information, but live leave data "
                "isn't connected to Orbit yet."
            ),
        ),
        OrbitIntent.EMS_ATTENDANCE: OrbitCapability(
            intent=OrbitIntent.EMS_ATTENDANCE,
            enabled=True,
            executor=OrbitExecutor.EMS_TOOL,
            unavailable_message=(
                "I understand you're asking about attendance information, but live attendance "
                "data isn't connected to Orbit yet."
            ),
        ),
        OrbitIntent.EMS_TIMESHEET: OrbitCapability(
            intent=OrbitIntent.EMS_TIMESHEET,
            enabled=True,
            executor=OrbitExecutor.EMS_TOOL,
            unavailable_message=(
                "I understand you're asking about timesheet information, but live timesheet "
                "data isn't connected to Orbit yet."
            ),
        ),
        OrbitIntent.EMS_ALLOCATION: OrbitCapability(
            intent=OrbitIntent.EMS_ALLOCATION,
            enabled=False,
            executor=OrbitExecutor.EMS_TOOL,
            unavailable_message=(
                "I understand you're asking about allocation information, but live allocation "
                "data isn't connected to Orbit yet."
            ),
        ),
        OrbitIntent.EMS_EMPLOYEE: OrbitCapability(
            intent=OrbitIntent.EMS_EMPLOYEE,
            enabled=True,
            executor=OrbitExecutor.EMS_TOOL,
            unavailable_message=(
                "I understand you're asking about employee lookup, but live employee data "
                "isn't connected to Orbit yet."
            ),
        ),
    }
)


def get_orbit_capability(intent: OrbitIntent) -> OrbitCapability | None:
    return ORBIT_CAPABILITIES.get(intent)
