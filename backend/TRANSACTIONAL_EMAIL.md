# Transactional email operations

Orbit writes email jobs to `email_outbox` in the same database transaction as the workflow event. FastAPI never sends these messages inline.

## Development

1. Copy the backend-only values from the repository `.env.example` into `.env` and replace placeholders.
2. Install dependencies: `backend/venv/Scripts/python.exe -m pip install -r backend/requirements.txt`.
3. Start the API from `backend`: `venv/Scripts/python.exe -m uvicorn app.main:app --reload`.
4. Start a separate worker from `backend`: `venv/Scripts/python.exe -m app.workers.email_worker`.

Use `--once` to drain currently due jobs and exit. Job states are `pending`, `processing`, `sent`, and `failed`; failures retry exponentially up to `EMAIL_MAX_ATTEMPTS`. Never run the worker with Vite-prefixed secrets.

## Production credentials

Set `GRAPH_AUTH_MODE=certificate` with `GRAPH_CERTIFICATE_PATH` (and an optional certificate password), or `GRAPH_AUTH_MODE=managed_identity` with an optional user-assigned `GRAPH_MANAGED_IDENTITY_CLIENT_ID`. Keep the same `EmailProvider` and worker.
