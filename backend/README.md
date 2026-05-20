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

# Configure SMTP (edit .env file)
# Set your Outlook email and password

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

Edit `backend/.env`:

```
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=VPendurthi@reknew.ai
SMTP_PASSWORD=Thankyouuniverse@33
SMTP_FROM=VPendurthi@reknew.ai
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
