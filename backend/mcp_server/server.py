"""Reknew Orbit MCP server.

This server exposes safe Reknew Orbit business actions as MCP tools.
The tools call the existing FastAPI backend instead of touching the database
directly, so permissions, validations, and audit behavior stay centralized.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP


API_BASE_URL = os.getenv("REKNEW_API_BASE_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REKNEW_MCP_REQUEST_TIMEOUT", "15"))

mcp = FastMCP("reknew-orbit")


def auth_headers(user_id: str, user_email: str, user_role: str = "employee") -> dict[str, str]:
    """Build the user context headers expected by the Reknew Orbit API."""
    return {
        "x-user-id": user_id,
        "x-user-email": user_email,
        "x-user-role": user_role,
    }


async def call_reknew_api(
    method: str,
    path: str,
    *,
    user_id: str,
    user_email: str,
    user_role: str = "employee",
    json_body: dict[str, Any] | None = None,
) -> Any:
    """Call the existing FastAPI backend with the current user context."""
    url = f"{API_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.request(
            method,
            url,
            headers=auth_headers(user_id, user_email, user_role),
            json=json_body,
        )

    try:
        payload = response.json()
    except ValueError:
        payload = {"message": response.text}

    if response.status_code >= 400:
        return {
            "success": False,
            "status_code": response.status_code,
            "error": payload,
        }

    return {
        "success": True,
        "status_code": response.status_code,
        "data": payload,
    }


@mcp.tool()
async def get_my_leave_balance(
    user_id: str,
    user_email: str,
    user_role: str = "employee",
) -> dict[str, Any]:
    """Get the current employee's leave balances and recent leave requests.

    Use this read-only tool when the user asks about available leave, pending
    leave, leave balance, or recent leave requests.
    """
    result = await call_reknew_api(
        "GET",
        "/leaves/me/summary",
        user_id=user_id,
        user_email=user_email,
        user_role=user_role,
    )

    if not result.get("success"):
        return result

    data = result.get("data") or {}
    balances = []
    for item in data.get("balances", []):
        balances.append(
            {
                "leave_type": item.get("name") or item.get("type"),
                "code": item.get("code"),
                "used": item.get("used"),
                "pending": item.get("pending"),
                "effective_available": item.get("effective_available") or item.get("available"),
                "total": item.get("total"),
                "expiry_label": item.get("expiry_label"),
            }
        )

    return {
        "success": True,
        "reporting_manager": data.get("reporting_manager"),
        "joining_date": data.get("joining_date"),
        "min_request_date": data.get("min_request_date"),
        "balances": balances,
        "recent_requests": data.get("requests", []),
    }


if __name__ == "__main__":
    mcp.run()
