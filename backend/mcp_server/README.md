# Reknew Orbit MCP Server

This MCP server exposes Reknew Orbit business actions as AI tools.

The first tool is read-only:

- `get_my_leave_balance`

It calls the existing FastAPI endpoint:

- `GET /api/v1/leaves/me/summary`

## Why This Design

The MCP server does not connect directly to Postgres. It calls the existing FastAPI APIs so existing permissions, validations, and business rules remain centralized.

## Environment

Optional environment variables:

```powershell
$env:REKNEW_API_BASE_URL = "http://127.0.0.1:8000/api/v1"
$env:REKNEW_MCP_REQUEST_TIMEOUT = "15"
```

## Run The FastAPI Backend First

From the project root:

```powershell
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Run The MCP Server

From the project root:

```powershell
python backend\mcp_server\server.py
```

The MCP server uses stdio transport by default.

## Tool User Context

Tools expect user context from the agent layer:

```json
{
  "user_id": "employee-id",
  "user_email": "employee@company.com",
  "user_role": "employee"
}
```

The MCP server forwards this context to FastAPI as:

- `x-user-id`
- `x-user-email`
- `x-user-role`

## Next Tools To Add

Recommended order:

1. `get_my_timesheet_status`
2. `get_my_pending_requests`
3. `apply_leave` with confirmation
4. `check_in`
5. `check_out`
