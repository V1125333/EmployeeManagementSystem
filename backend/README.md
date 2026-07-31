# Reknew Orbit — Backend API

FastAPI backend with real Outlook SMTP email integration.

## Quick Start

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Configure the backend (edit backend/.env)
# At minimum, set AUTH_JWT_SECRET to a long random value.

# Run server
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | App info |
| GET | `/health` | Health check + SMTP status |
| POST | `/api/v1/employees/` | Add employee + send email |

## SMTP Setup

The backend always loads server configuration from `backend/.env`, regardless
of the shell's current directory. Create a strong JWT secret:

```powershell
venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Add the generated value to `backend/.env`:

```dotenv
AUTH_JWT_SECRET=paste-the-generated-value-here
```

The application refuses to start if this value is missing or shorter than 32
characters. `backend/.env` is gitignored; never commit its contents.

## Contextual LLM shadow provider

Phase A remains observation-only. To run it with OpenAI, add the following to
the gitignored `backend/.env`:

```dotenv
CONTEXTUAL_LLM_ENABLED=true
CONTEXTUAL_LLM_SHADOW_MODE=true
CONTEXTUAL_LLM_PROVIDER=openai
CONTEXTUAL_LLM_MODEL=your-approved-structured-output-model
CONTEXTUAL_LLM_API_KEY=your-server-side-provider-key
CONTEXTUAL_LLM_BASE_URL=https://api.openai.com/v1
CONTEXTUAL_LLM_TIMEOUT_SECONDS=4
CONTEXTUAL_LLM_RETRY_COUNT=1
CONTEXTUAL_LLM_MAX_INPUT_TOKENS=6000
CONTEXTUAL_LLM_MAX_OUTPUT_TOKENS=700
CONTEXTUAL_LLM_TEMPERATURE=0
CONTEXTUAL_LLM_PROMPT_VERSION=contextual_leave_interpreter_v2
```

Startup fails clearly if shadow mode, provider, model, credential, HTTPS URL,
timeout, retry, token budget, or prompt version is invalid. Provider secrets
must never use a `VITE_` prefix.

Run the checked-in zero-shot/few-shot comparison after configuration:

```powershell
venv\Scripts\python.exe scripts\evaluate_contextual_shadow.py `
  --prompt-mode both `
  --output contextual-shadow-provider-results.json
```

The generated result file can contain model classifications and should remain
outside source control. Authenticated admins can inspect safe runtime status at
`GET /api/v1/ai/shadow-provider-status`; the response never includes the API
key.

For legacy SMTP configuration, use environment-specific values rather than
committed credentials:

```
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=your-mailbox@example.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-mailbox@example.com
```

**For testing:** sender and receiver can be the same email.

**Note:** If using Microsoft 365 with MFA enabled, you'll need to create an App Password:
1. Go to https://account.microsoft.com/security
2. Security → Advanced security options
3. App passwords → Create a new app password
4. Use that password in SMTP_PASSWORD

## Test the API

```bash
# Health check
curl http://localhost:8000/health

# Add employee (with email)
curl -X POST http://localhost:8000/api/v1/employees/ \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "work_email": "your_outlook_email@outlook.com",
    "phone": "1234567890",
    "workforce_type": "Full-Time Employee",
    "role": "Engineer",
    "department": "Engineering",
    "reporting_manager": "David Park",
    "joining_date": "2026-05-20",
    "work_location": "Remote",
    "send_welcome_email": true,
    "create_checklist": true
  }'
```

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── employees.py       # API routes
│   ├── core/
│   │   └── config.py          # Environment config
│   ├── models/                 # SQLAlchemy models (future)
│   ├── schemas/
│   │   └── employee.py        # Pydantic schemas
│   ├── services/
│   │   ├── email_service.py   # Outlook SMTP integration
│   │   └── employee_service.py # Business logic
│   └── main.py                # FastAPI app entry
├── .env                        # Environment variables
└── requirements.txt
```
