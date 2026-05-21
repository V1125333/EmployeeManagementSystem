"""
Seed script — adds 15 dummy employees for testing.
Run: python seed_dummy.py
"""

import sys
sys.path.insert(0, ".")

from datetime import date
from app.core.database import SessionLocal, create_tables
from app.models.employee import Employee
from app.services.auth_service import generate_setup_code

create_tables()
db = SessionLocal()

DUMMY_EMPLOYEES = [
    {
        "first_name": "Priya", "last_name": "Sharma",
        "work_email": "priya.sharma@reknew.ai", "phone": "9876543210",
        "date_of_birth": date(1998, 3, 15), "gender": "female",
        "department": "Engineering", "designation": "Engineering Lead",
        "role": "manager", "workforce_type": "Full-Time Employee",
        "reporting_manager": "Venu Pendurthi", "work_location": "Onshore",
        "joining_date": date(2023, 6, 10), "employment_status": "active",
    },
    {
        "first_name": "David", "last_name": "Park",
        "work_email": "david.park@reknew.ai", "phone": "9876543211",
        "date_of_birth": date(1990, 7, 22), "gender": "male",
        "department": "Product", "designation": "VP Product",
        "role": "manager", "workforce_type": "Full-Time Employee",
        "reporting_manager": "Venu Pendurthi", "work_location": "Remote",
        "joining_date": date(2022, 1, 15), "employment_status": "active",
    },
    {
        "first_name": "Sarah", "last_name": "Chen",
        "work_email": "sarah.chen@reknew.ai", "phone": "9876543212",
        "date_of_birth": date(1995, 11, 8), "gender": "female",
        "department": "People", "designation": "People Officer",
        "role": "hr_admin", "workforce_type": "Full-Time Employee",
        "reporting_manager": "Venu Pendurthi", "work_location": "Onshore",
        "joining_date": date(2023, 3, 1), "employment_status": "active",
    },
    {
        "first_name": "Marcus", "last_name": "Chen",
        "work_email": "marcus.chen@reknew.ai", "phone": "9876543213",
        "date_of_birth": date(1996, 5, 30), "gender": "male",
        "department": "Product", "designation": "Product Manager",
        "role": "employee", "workforce_type": "Full-Time Employee",
        "reporting_manager": "David Park", "work_location": "Remote",
        "joining_date": date(2023, 9, 12), "employment_status": "active",
    },
    {
        "first_name": "Maya", "last_name": "Patel",
        "work_email": "maya.patel@reknew.ai", "phone": "9876543214",
        "date_of_birth": date(1997, 12, 3), "gender": "female",
        "department": "Engineering", "designation": "Data Analyst",
        "role": "employee", "workforce_type": "Full-Time Employee",
        "reporting_manager": "Priya Sharma", "work_location": "Onshore",
        "joining_date": date(2024, 1, 8), "employment_status": "active",
    },
    {
        "first_name": "Tom", "last_name": "Keller",
        "work_email": "tom.keller@reknew.ai", "phone": "9876543215",
        "date_of_birth": date(1994, 8, 17), "gender": "male",
        "department": "Design", "designation": "Senior Designer",
        "role": "employee", "workforce_type": "Full-Time Employee",
        "reporting_manager": "David Park", "work_location": "Hybrid",
        "joining_date": date(2023, 4, 20), "employment_status": "active",
    },
    {
        "first_name": "Lin", "last_name": "Chen",
        "work_email": "lin.chen@reknew.ai", "phone": "9876543216",
        "date_of_birth": date(1999, 2, 25), "gender": "female",
        "department": "Engineering", "designation": "Software Engineer",
        "role": "employee", "workforce_type": "Full-Time Employee",
        "reporting_manager": "Priya Sharma", "work_location": "Onshore",
        "joining_date": date(2024, 3, 15), "employment_status": "active",
    },
    {
        "first_name": "James", "last_name": "Rivera",
        "work_email": "james.rivera@reknew.ai", "phone": "9876543217",
        "date_of_birth": date(1993, 6, 11), "gender": "male",
        "department": "Sales", "designation": "Sales Lead",
        "role": "manager", "workforce_type": "Full-Time Employee",
        "reporting_manager": "Venu Pendurthi", "work_location": "Onshore",
        "joining_date": date(2022, 8, 1), "employment_status": "active",
    },
    {
        "first_name": "Aaliyah", "last_name": "Brooks",
        "work_email": "aaliyah.brooks@reknew.ai", "phone": "9876543218",
        "date_of_birth": date(2000, 9, 5), "gender": "female",
        "department": "Marketing", "designation": "Marketing Specialist",
        "role": "employee", "workforce_type": "Full-Time Employee",
        "reporting_manager": "James Rivera", "work_location": "Remote",
        "joining_date": date(2024, 5, 1), "employment_status": "active",
    },
    {
        "first_name": "Raj", "last_name": "Kapoor",
        "work_email": "raj.kapoor@reknew.ai", "phone": "9876543219",
        "date_of_birth": date(1991, 1, 20), "gender": "male",
        "department": "Finance", "designation": "Finance Manager",
        "role": "employee", "workforce_type": "Full-Time Employee",
        "reporting_manager": "Venu Pendurthi", "work_location": "Onshore",
        "joining_date": date(2023, 2, 14), "employment_status": "active",
    },
    {
        "first_name": "Sofia", "last_name": "Reyes",
        "work_email": "sofia.reyes@reknew.ai", "phone": "9876543220",
        "date_of_birth": date(1998, 4, 12), "gender": "female",
        "department": "Design", "designation": "UX Designer",
        "role": "employee", "workforce_type": "Full-Time Employee",
        "reporting_manager": "Tom Keller", "work_location": "Hybrid",
        "joining_date": date(2024, 7, 1), "employment_status": "active",
    },
    {
        "first_name": "Amir", "last_name": "Hassan",
        "work_email": "amir.hassan@reknew.ai", "phone": "9876543221",
        "date_of_birth": date(1997, 10, 28), "gender": "male",
        "department": "Engineering", "designation": "DevOps Engineer",
        "role": "employee", "workforce_type": "Full-Time Employee",
        "reporting_manager": "Priya Sharma", "work_location": "Remote",
        "joining_date": date(2024, 2, 5), "employment_status": "active",
    },
    {
        "first_name": "Neha", "last_name": "Gupta",
        "work_email": "neha.gupta@reknew.ai", "phone": "9876543222",
        "date_of_birth": date(2001, 6, 18), "gender": "female",
        "department": "Engineering", "designation": "Junior Engineer",
        "role": "trainee", "workforce_type": "Paid Intern",
        "reporting_manager": "Priya Sharma", "work_location": "Onshore",
        "joining_date": date(2026, 4, 1), "employment_status": "active",
    },
    {
        "first_name": "Kevin", "last_name": "Wright",
        "work_email": "kevin.wright@reknew.ai", "phone": "9876543223",
        "date_of_birth": date(1992, 3, 7), "gender": "male",
        "department": "Operations", "designation": "Operations Manager",
        "role": "employee", "workforce_type": "Full-Time Employee",
        "reporting_manager": "Venu Pendurthi", "work_location": "Onshore",
        "joining_date": date(2023, 11, 1), "employment_status": "inactive",
        "inactive_reason": "long_term_leave",
    },
    {
        "first_name": "Ananya", "last_name": "Reddy",
        "work_email": "ananya.reddy@reknew.ai", "phone": "9876543224",
        "date_of_birth": date(1999, 8, 14), "gender": "female",
        "department": "Sales", "designation": "Sales Executive",
        "role": "employee", "workforce_type": "Full-Time Employee",
        "reporting_manager": "James Rivera", "work_location": "Onshore",
        "joining_date": date(2025, 1, 10), "employment_status": "active",
    },
]

# Seed
added = 0
for emp_data in DUMMY_EMPLOYEES:
    existing = db.query(Employee).filter(Employee.work_email == emp_data["work_email"]).first()
    if existing:
        print(f"  ⏭  {emp_data['work_email']} already exists")
        continue

    setup_code = generate_setup_code(emp_data["last_name"], emp_data.get("date_of_birth"))

    emp = Employee(
        **emp_data,
        setup_code=setup_code,
        is_first_login=True,
        is_active=emp_data.get("employment_status") == "active",
    )
    db.add(emp)
    added += 1
    print(f"  ✅ {emp_data['first_name']} {emp_data['last_name']} ({emp_data['work_email']}) — Setup: {setup_code}")

db.commit()
db.close()

print(f"\nDone! Added {added} employees.")
print("Run 'uvicorn app.main:app --reload --port 8000' to start the server.")
