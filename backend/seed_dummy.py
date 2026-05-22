"""
Seed script — populates ALL tables with realistic dummy data for testing.
Run: python seed_dummy.py
"""

import sys
sys.path.insert(0, ".")

from datetime import date, datetime, timedelta
import random
from app.core.database import SessionLocal, create_tables
from app.models.employee import Employee
from app.models.organization import Department, Designation
from app.models.leave_attendance import LeaveType, LeaveBalance, LeaveRequest, Attendance, AttendanceCorrection
from app.models.training import OnboardingTask, Training, TrainingEnrollment
from app.models.chat import Channel, ChannelMember, Message
from app.models.operations import Project, Allocation, Announcement, Notification
from app.services.auth_service import generate_setup_code

create_tables()
db = SessionLocal()

# ═══════════════════════════════════════
# 0. SEED BASE DATA (departments, leave types, channels) if missing
# ═══════════════════════════════════════
from app.models.organization import Department, Designation
from app.models.chat import Channel

if db.query(Department).count() == 0:
    for name, code, order in [("Engineering","ENG",1),("Product","PRD",2),("Design","DES",3),("Marketing","MKT",4),
                               ("Sales","SLS",5),("Operations","OPS",6),("People","PPL",7),("Finance","FIN",8)]:
        db.add(Department(name=name, code=code, sort_order=order))
    db.commit()
    print("  Seeded departments")

if db.query(LeaveType).count() == 0:
    for name, code, days, paid, carry, max_carry, order in [
        ("Casual Leave","CL",12,True,True,5,1),("Sick Leave","SL",10,True,False,0,2),
        ("Earned Leave","EL",15,True,True,10,3),("Maternity Leave","ML",180,True,False,0,4),
        ("Paternity Leave","PL",15,True,False,0,5),("Compensatory Off","CO",0,True,False,0,6),
        ("Loss of Pay","LOP",0,False,False,0,7),("Bereavement Leave","BL",5,True,False,0,8)]:
        db.add(LeaveType(name=name, code=code, default_days_per_year=days,
                         is_paid=paid, is_carry_forward=carry, max_carry_forward_days=max_carry, sort_order=order))
    db.commit()
    print("  Seeded leave types")

if db.query(Channel).count() == 0:
    for name, ch_type, desc in [("general","public","General"),("announcements","public","Announcements"),
                                 ("engineering","public","Engineering"),("product","public","Product"),
                                 ("design","public","Design"),("random","public","Random")]:
        db.add(Channel(name=name, type=ch_type, description=desc))
    db.commit()
    print("  Seeded channels")

# Seed super admin
from app.services.auth_service import hash_password as hp
admin = db.query(Employee).filter(Employee.work_email == "superadmin@reknew.ai").first()
if not admin:
    from datetime import date as d2
    admin = Employee(first_name="Super", last_name="Admin", work_email="superadmin@reknew.ai",
                     phone="0000000000", workforce_type="Full-Time Employee", role="super_admin",
                     department="People", designation="Administrator", reporting_manager="Self",
                     employment_status="active", work_location="Onshore", joining_date=d2(2024,1,1),
                     password_hash=hp("test"), is_first_login=False, is_active=True)
    db.add(admin)
    db.commit()
    print("  Seeded super admin")

# ═══════════════════════════════════════
# 1. EMPLOYEES (15 dummy)
# ═══════════════════════════════════════
print("\n═══ SEEDING EMPLOYEES ═══")

DUMMY_EMPLOYEES = [
    {"first_name": "Priya", "last_name": "Sharma", "work_email": "priya.sharma@reknew.ai", "phone": "9876543210",
     "date_of_birth": date(1998, 3, 15), "gender": "female", "department": "Engineering", "designation": "Engineering Lead",
     "role": "manager", "workforce_type": "Full-Time Employee", "reporting_manager": "Venu Pendurthi",
     "work_location": "Onshore", "joining_date": date(2023, 6, 10), "employment_status": "active"},

    {"first_name": "David", "last_name": "Park", "work_email": "david.park@reknew.ai", "phone": "9876543211",
     "date_of_birth": date(1990, 7, 22), "gender": "male", "department": "Product", "designation": "VP Product",
     "role": "manager", "workforce_type": "Full-Time Employee", "reporting_manager": "Venu Pendurthi",
     "work_location": "Remote", "joining_date": date(2022, 1, 15), "employment_status": "active"},

    {"first_name": "Sarah", "last_name": "Chen", "work_email": "sarah.chen@reknew.ai", "phone": "9876543212",
     "date_of_birth": date(1995, 11, 8), "gender": "female", "department": "People", "designation": "People Officer",
     "role": "hr_admin", "workforce_type": "Full-Time Employee", "reporting_manager": "Venu Pendurthi",
     "work_location": "Onshore", "joining_date": date(2023, 3, 1), "employment_status": "active"},

    {"first_name": "Marcus", "last_name": "Chen", "work_email": "marcus.chen@reknew.ai", "phone": "9876543213",
     "date_of_birth": date(1996, 5, 30), "gender": "male", "department": "Product", "designation": "Product Manager",
     "role": "employee", "workforce_type": "Full-Time Employee", "reporting_manager": "David Park",
     "work_location": "Remote", "joining_date": date(2023, 9, 12), "employment_status": "active"},

    {"first_name": "Maya", "last_name": "Patel", "work_email": "maya.patel@reknew.ai", "phone": "9876543214",
     "date_of_birth": date(1997, 12, 3), "gender": "female", "department": "Engineering", "designation": "Data Analyst",
     "role": "employee", "workforce_type": "Full-Time Employee", "reporting_manager": "Priya Sharma",
     "work_location": "Onshore", "joining_date": date(2024, 1, 8), "employment_status": "active"},

    {"first_name": "Tom", "last_name": "Keller", "work_email": "tom.keller@reknew.ai", "phone": "9876543215",
     "date_of_birth": date(1994, 8, 17), "gender": "male", "department": "Design", "designation": "Senior Designer",
     "role": "employee", "workforce_type": "Full-Time Employee", "reporting_manager": "David Park",
     "work_location": "Hybrid", "joining_date": date(2023, 4, 20), "employment_status": "active"},

    {"first_name": "Lin", "last_name": "Chen", "work_email": "lin.chen@reknew.ai", "phone": "9876543216",
     "date_of_birth": date(1999, 2, 25), "gender": "female", "department": "Engineering", "designation": "Software Engineer",
     "role": "employee", "workforce_type": "Full-Time Employee", "reporting_manager": "Priya Sharma",
     "work_location": "Onshore", "joining_date": date(2024, 3, 15), "employment_status": "active"},

    {"first_name": "James", "last_name": "Rivera", "work_email": "james.rivera@reknew.ai", "phone": "9876543217",
     "date_of_birth": date(1993, 6, 11), "gender": "male", "department": "Sales", "designation": "Sales Lead",
     "role": "manager", "workforce_type": "Full-Time Employee", "reporting_manager": "Venu Pendurthi",
     "work_location": "Onshore", "joining_date": date(2022, 8, 1), "employment_status": "active"},

    {"first_name": "Aaliyah", "last_name": "Brooks", "work_email": "aaliyah.brooks@reknew.ai", "phone": "9876543218",
     "date_of_birth": date(2000, 9, 5), "gender": "female", "department": "Marketing", "designation": "Marketing Specialist",
     "role": "employee", "workforce_type": "Full-Time Employee", "reporting_manager": "James Rivera",
     "work_location": "Remote", "joining_date": date(2024, 5, 1), "employment_status": "active"},

    {"first_name": "Raj", "last_name": "Kapoor", "work_email": "raj.kapoor@reknew.ai", "phone": "9876543219",
     "date_of_birth": date(1991, 1, 20), "gender": "male", "department": "Finance", "designation": "Finance Manager",
     "role": "employee", "workforce_type": "Full-Time Employee", "reporting_manager": "Venu Pendurthi",
     "work_location": "Onshore", "joining_date": date(2023, 2, 14), "employment_status": "active"},

    {"first_name": "Sofia", "last_name": "Reyes", "work_email": "sofia.reyes@reknew.ai", "phone": "9876543220",
     "date_of_birth": date(1998, 4, 12), "gender": "female", "department": "Design", "designation": "UX Designer",
     "role": "employee", "workforce_type": "Full-Time Employee", "reporting_manager": "Tom Keller",
     "work_location": "Hybrid", "joining_date": date(2024, 7, 1), "employment_status": "active"},

    {"first_name": "Amir", "last_name": "Hassan", "work_email": "amir.hassan@reknew.ai", "phone": "9876543221",
     "date_of_birth": date(1997, 10, 28), "gender": "male", "department": "Engineering", "designation": "DevOps Engineer",
     "role": "employee", "workforce_type": "Full-Time Employee", "reporting_manager": "Priya Sharma",
     "work_location": "Remote", "joining_date": date(2024, 2, 5), "employment_status": "active"},

    {"first_name": "Neha", "last_name": "Gupta", "work_email": "neha.gupta@reknew.ai", "phone": "9876543222",
     "date_of_birth": date(2001, 6, 18), "gender": "female", "department": "Engineering", "designation": "Junior Engineer",
     "role": "trainee", "workforce_type": "Paid Intern", "reporting_manager": "Priya Sharma",
     "work_location": "Onshore", "joining_date": date(2026, 4, 1), "employment_status": "active"},

    {"first_name": "Kevin", "last_name": "Wright", "work_email": "kevin.wright@reknew.ai", "phone": "9876543223",
     "date_of_birth": date(1992, 3, 7), "gender": "male", "department": "Operations", "designation": "Operations Manager",
     "role": "employee", "workforce_type": "Full-Time Employee", "reporting_manager": "Venu Pendurthi",
     "work_location": "Onshore", "joining_date": date(2023, 11, 1), "employment_status": "inactive",
     "inactive_reason": "long_term_leave"},

    {"first_name": "Ananya", "last_name": "Reddy", "work_email": "ananya.reddy@reknew.ai", "phone": "9876543224",
     "date_of_birth": date(1999, 8, 14), "gender": "female", "department": "Sales", "designation": "Sales Executive",
     "role": "employee", "workforce_type": "Full-Time Employee", "reporting_manager": "James Rivera",
     "work_location": "Onshore", "joining_date": date(2025, 1, 10), "employment_status": "active"},
]

emp_ids = {}
added = 0
for emp_data in DUMMY_EMPLOYEES:
    existing = db.query(Employee).filter(Employee.work_email == emp_data["work_email"]).first()
    if existing:
        emp_ids[emp_data["work_email"]] = existing.id
        print(f"  ⏭  {emp_data['work_email']} exists")
        continue

    setup_code = generate_setup_code(emp_data["last_name"], emp_data.get("date_of_birth"))
    emp = Employee(**emp_data, setup_code=setup_code, is_first_login=True,
                   is_active=emp_data.get("employment_status") == "active")
    db.add(emp)
    db.flush()
    emp_ids[emp_data["work_email"]] = emp.id
    added += 1
    print(f"  ✅ {emp_data['first_name']} {emp_data['last_name']} — {setup_code}")

db.commit()
print(f"  Employees: {added} added")

# Get super admin id
admin = db.query(Employee).filter(Employee.work_email == "superadmin@reknew.ai").first()
admin_id = admin.id if admin else None

# Get all employee IDs
all_emps = db.query(Employee).filter(Employee.work_email != "superadmin@reknew.ai").all()
all_emp_ids = [e.id for e in all_emps]
active_emps = [e for e in all_emps if e.employment_status == "active"]

# ═══════════════════════════════════════
# 2. LEAVE BALANCES (for all active employees)
# ═══════════════════════════════════════
print("\n═══ SEEDING LEAVE BALANCES ═══")

leave_types = db.query(LeaveType).all()
lt_map = {lt.code: lt for lt in leave_types}
year = 2026

bal_added = 0
for emp in active_emps:
    existing = db.query(LeaveBalance).filter(LeaveBalance.employee_id == emp.id, LeaveBalance.year == year).first()
    if existing:
        continue
    for lt in leave_types:
        if lt.default_days_per_year > 0:
            used = random.randint(0, min(5, int(lt.default_days_per_year)))
            db.add(LeaveBalance(
                employee_id=emp.id, leave_type_id=lt.id, year=year,
                total_days=lt.default_days_per_year, used_days=used, carry_forward_days=0,
            ))
            bal_added += 1
db.commit()
print(f"  Leave balances: {bal_added} added")

# ═══════════════════════════════════════
# 3. LEAVE REQUESTS (mix of pending, approved, rejected)
# ═══════════════════════════════════════
print("\n═══ SEEDING LEAVE REQUESTS ═══")

if db.query(LeaveRequest).count() == 0:
    cl_id = lt_map["CL"].id
    sl_id = lt_map["SL"].id
    el_id = lt_map["EL"].id

    leave_requests = [
        # Pending requests
        {"employee_id": emp_ids.get("maya.patel@reknew.ai"), "leave_type_id": cl_id,
         "start_date": date(2026, 5, 26), "end_date": date(2026, 5, 28), "total_days": 3,
         "reason": "Family event", "status": "pending"},
        {"employee_id": emp_ids.get("tom.keller@reknew.ai"), "leave_type_id": sl_id,
         "start_date": date(2026, 5, 27), "end_date": date(2026, 5, 27), "total_days": 1,
         "reason": "Doctor appointment", "status": "pending"},
        {"employee_id": emp_ids.get("lin.chen@reknew.ai"), "leave_type_id": cl_id,
         "start_date": date(2026, 5, 29), "end_date": date(2026, 5, 30), "total_days": 2,
         "reason": "Personal work", "status": "pending"},
        {"employee_id": emp_ids.get("aaliyah.brooks@reknew.ai"), "leave_type_id": el_id,
         "start_date": date(2026, 6, 2), "end_date": date(2026, 6, 6), "total_days": 5,
         "reason": "Vacation", "status": "pending"},
        # Approved (currently on leave)
        {"employee_id": emp_ids.get("marcus.chen@reknew.ai"), "leave_type_id": cl_id,
         "start_date": date(2026, 5, 21), "end_date": date(2026, 5, 22), "total_days": 2,
         "reason": "Moving to new apartment", "status": "approved",
         "reviewed_by": admin_id, "reviewed_at": datetime(2026, 5, 19, 10, 0)},
        {"employee_id": emp_ids.get("sofia.reyes@reknew.ai"), "leave_type_id": sl_id,
         "start_date": date(2026, 5, 21), "end_date": date(2026, 5, 21), "total_days": 1,
         "reason": "Not feeling well", "status": "approved",
         "reviewed_by": admin_id, "reviewed_at": datetime(2026, 5, 20, 14, 30)},
        # Past approved
        {"employee_id": emp_ids.get("priya.sharma@reknew.ai"), "leave_type_id": cl_id,
         "start_date": date(2026, 5, 12), "end_date": date(2026, 5, 13), "total_days": 2,
         "reason": "Family function", "status": "approved",
         "reviewed_by": admin_id, "reviewed_at": datetime(2026, 5, 10, 9, 0)},
        {"employee_id": emp_ids.get("james.rivera@reknew.ai"), "leave_type_id": el_id,
         "start_date": date(2026, 5, 5), "end_date": date(2026, 5, 9), "total_days": 5,
         "reason": "Annual vacation", "status": "approved",
         "reviewed_by": admin_id, "reviewed_at": datetime(2026, 5, 1, 11, 0)},
        # Rejected
        {"employee_id": emp_ids.get("amir.hassan@reknew.ai"), "leave_type_id": cl_id,
         "start_date": date(2026, 5, 15), "end_date": date(2026, 5, 16), "total_days": 2,
         "reason": "Short trip", "status": "rejected",
         "reviewed_by": admin_id, "reviewed_at": datetime(2026, 5, 14, 16, 0),
         "reviewer_notes": "Critical release this week, please reschedule"},
    ]

    for lr_data in leave_requests:
        if lr_data.get("employee_id"):
            db.add(LeaveRequest(**lr_data))
    db.commit()
    print(f"  Leave requests: {len(leave_requests)} added")
else:
    print("  ⏭  Leave requests exist")

# ═══════════════════════════════════════
# 4. ATTENDANCE (last 10 working days)
# ═══════════════════════════════════════
print("\n═══ SEEDING ATTENDANCE ═══")

if db.query(Attendance).count() == 0:
    today = date(2026, 5, 21)
    att_added = 0
    for day_offset in range(14):
        d = today - timedelta(days=day_offset)
        if d.weekday() >= 5:  # skip weekends
            continue
        for emp in active_emps:
            roll = random.random()
            if roll < 0.85:
                status = "present"
                cin = datetime(d.year, d.month, d.day, random.randint(8, 9), random.randint(0, 59))
                cout = datetime(d.year, d.month, d.day, random.randint(17, 19), random.randint(0, 59))
                hours = round((cout - cin).total_seconds() / 3600, 2)
            elif roll < 0.92:
                status = "wfh"
                cin = datetime(d.year, d.month, d.day, random.randint(9, 10), random.randint(0, 59))
                cout = datetime(d.year, d.month, d.day, random.randint(17, 18), random.randint(0, 59))
                hours = round((cout - cin).total_seconds() / 3600, 2)
            elif roll < 0.96:
                status = "late"
                cin = datetime(d.year, d.month, d.day, random.randint(10, 11), random.randint(0, 59))
                cout = datetime(d.year, d.month, d.day, random.randint(18, 20), random.randint(0, 59))
                hours = round((cout - cin).total_seconds() / 3600, 2)
            else:
                status = random.choice(["absent", "on_leave"])
                cin, cout, hours = None, None, None

            db.add(Attendance(
                employee_id=emp.id, date=d, check_in=cin, check_out=cout,
                total_hours=hours, status=status, source="system",
            ))
            att_added += 1
    db.commit()
    print(f"  Attendance records: {att_added} added")
else:
    print("  ⏭  Attendance exists")

# ═══════════════════════════════════════
# 5. ATTENDANCE CORRECTIONS (2 pending)
# ═══════════════════════════════════════
print("\n═══ SEEDING ATTENDANCE CORRECTIONS ═══")

if db.query(AttendanceCorrection).count() == 0:
    recent_att = db.query(Attendance).filter(Attendance.status == "absent").limit(2).all()
    for att in recent_att:
        db.add(AttendanceCorrection(
            employee_id=att.employee_id, attendance_id=att.id,
            requested_check_in=datetime(att.date.year, att.date.month, att.date.day, 9, 0),
            requested_check_out=datetime(att.date.year, att.date.month, att.date.day, 18, 0),
            reason="Forgot to mark attendance, was working from home",
            status="pending",
        ))
    db.commit()
    print(f"  Attendance corrections: {len(recent_att)} added")
else:
    print("  ⏭  Corrections exist")

# ═══════════════════════════════════════
# 6. TRAININGS + ENROLLMENTS
# ═══════════════════════════════════════
print("\n═══ SEEDING TRAININGS ═══")

if db.query(Training).count() == 0:
    trainings_data = [
        {"title": "Company Security Awareness", "type": "compliance", "is_mandatory": True,
         "duration_hours": 2, "due_date": date(2026, 6, 30)},
        {"title": "React Advanced Patterns", "type": "skill_based", "is_mandatory": False,
         "duration_hours": 8, "due_date": date(2026, 7, 15)},
        {"title": "Leadership Fundamentals", "type": "optional", "is_mandatory": False,
         "duration_hours": 4, "due_date": date(2026, 8, 1)},
        {"title": "Data Privacy & GDPR", "type": "compliance", "is_mandatory": True,
         "duration_hours": 1.5, "due_date": date(2026, 6, 15)},
        {"title": "Effective Communication", "type": "optional", "is_mandatory": False,
         "duration_hours": 3, "due_date": date(2026, 7, 30)},
    ]
    training_ids = []
    for td in trainings_data:
        t = Training(**td, created_by=admin_id)
        db.add(t)
        db.flush()
        training_ids.append(t.id)
        print(f"  ✅ Training: {td['title']}")

    # Enroll employees
    enroll_count = 0
    for emp in active_emps:
        for tid in training_ids[:2]:  # Mandatory ones for everyone
            status = random.choice(["pending", "in_progress", "completed"])
            db.add(TrainingEnrollment(
                training_id=tid, employee_id=emp.id, status=status,
                started_at=datetime(2026, 5, 1) if status != "pending" else None,
                completed_at=datetime(2026, 5, 15) if status == "completed" else None,
                score=random.randint(75, 100) if status == "completed" else None,
            ))
            enroll_count += 1
        # Random optional ones
        if random.random() > 0.5:
            tid = random.choice(training_ids[2:])
            db.add(TrainingEnrollment(
                training_id=tid, employee_id=emp.id, status="pending",
            ))
            enroll_count += 1

    db.commit()
    print(f"  Training enrollments: {enroll_count} added")
else:
    print("  ⏭  Trainings exist")

# ═══════════════════════════════════════
# 7. PROJECTS + ALLOCATIONS
# ═══════════════════════════════════════
print("\n═══ SEEDING PROJECTS ═══")

if db.query(Project).count() == 0:
    projects_data = [
        {"name": "Platform Redesign", "code": "PLT-001", "client_name": "Internal",
         "status": "active", "start_date": date(2026, 1, 15)},
        {"name": "Client Onboarding v3", "code": "COB-003", "client_name": "Acme Corp",
         "status": "active", "start_date": date(2026, 3, 1)},
        {"name": "Analytics Dashboard", "code": "ADB-001", "client_name": "Internal",
         "status": "active", "start_date": date(2026, 4, 10)},
        {"name": "Mobile App MVP", "code": "MOB-001", "client_name": "Internal",
         "status": "planning", "start_date": date(2026, 7, 1)},
    ]

    proj_ids = []
    for pd in projects_data:
        p = Project(**pd, created_by=admin_id)
        db.add(p)
        db.flush()
        proj_ids.append(p.id)
        print(f"  ✅ Project: {pd['name']}")

    # Allocations
    allocations_data = [
        (emp_ids.get("priya.sharma@reknew.ai"), proj_ids[0], 60, "Engineering Lead"),
        (emp_ids.get("lin.chen@reknew.ai"), proj_ids[0], 100, "Frontend Engineer"),
        (emp_ids.get("tom.keller@reknew.ai"), proj_ids[0], 50, "UI Designer"),
        (emp_ids.get("maya.patel@reknew.ai"), proj_ids[2], 100, "Data Analyst"),
        (emp_ids.get("marcus.chen@reknew.ai"), proj_ids[1], 80, "Product Manager"),
        (emp_ids.get("amir.hassan@reknew.ai"), proj_ids[0], 40, "DevOps"),
        (emp_ids.get("amir.hassan@reknew.ai"), proj_ids[2], 60, "DevOps"),
        (emp_ids.get("priya.sharma@reknew.ai"), proj_ids[1], 40, "Tech Advisor"),
        (emp_ids.get("sofia.reyes@reknew.ai"), proj_ids[1], 100, "UX Designer"),
        (emp_ids.get("james.rivera@reknew.ai"), proj_ids[1], 30, "Sales Lead"),
        (emp_ids.get("aaliyah.brooks@reknew.ai"), proj_ids[1], 50, "Marketing"),
    ]

    alloc_count = 0
    for eid, pid, pct, role in allocations_data:
        if eid and pid:
            db.add(Allocation(
                employee_id=eid, project_id=pid, allocation_percentage=pct,
                role_in_project=role, start_date=date(2026, 1, 15), is_active=True,
            ))
            alloc_count += 1

    db.commit()
    print(f"  Allocations: {alloc_count} added")
else:
    print("  ⏭  Projects exist")

# ═══════════════════════════════════════
# 8. ANNOUNCEMENTS
# ═══════════════════════════════════════
print("\n═══ SEEDING ANNOUNCEMENTS ═══")

if db.query(Announcement).count() == 0:
    announcements = [
        {"title": "Q2 All-Hands Meeting", "description": "Join us for the Q2 all-hands meeting this Friday at 3 PM EST. We'll review progress and upcoming plans.",
         "type": "general", "is_pinned": True, "publish_date": date(2026, 5, 19)},
        {"title": "Benefits Enrollment Open", "description": "Benefits enrollment for 2026 is now open. Please review your selections in Gusto by May 30.",
         "type": "hr", "is_pinned": False, "publish_date": date(2026, 5, 15)},
        {"title": "New Remote Work Policy", "description": "Updated remote work policy effective June 1. Employees can work remotely up to 3 days per week with manager approval.",
         "type": "policy", "is_pinned": False, "publish_date": date(2026, 5, 10)},
    ]
    for a in announcements:
        db.add(Announcement(**a, published_by=admin_id))
    db.commit()
    print(f"  Announcements: {len(announcements)} added")
else:
    print("  ⏭  Announcements exist")

# ═══════════════════════════════════════
# 9. NOTIFICATIONS
# ═══════════════════════════════════════
print("\n═══ SEEDING NOTIFICATIONS ═══")

if db.query(Notification).count() == 0 and admin_id:
    notifications = [
        {"user_id": admin_id, "title": "Leave request from Maya Patel", "message": "Maya has requested 3 days casual leave (May 26-28)", "type": "leave", "is_read": False},
        {"user_id": admin_id, "title": "Leave request from Tom Keller", "message": "Tom has requested 1 day sick leave (May 27)", "type": "leave", "is_read": False},
        {"user_id": admin_id, "title": "Attendance correction pending", "message": "2 attendance correction requests are waiting for approval", "type": "attendance", "is_read": False},
        {"user_id": admin_id, "title": "Training deadline approaching", "message": "Data Privacy & GDPR training is due in 25 days. 5 employees haven't started.", "type": "training", "is_read": True},
        {"user_id": admin_id, "title": "New employee onboarding", "message": "Neha Gupta (Trainee) has joined. First-time setup is pending.", "type": "system", "is_read": True},
    ]
    for n in notifications:
        db.add(Notification(**n))
    db.commit()
    print(f"  Notifications: {len(notifications)} added")
else:
    print("  ⏭  Notifications exist")

# ═══════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════
print("\n═══ SEED COMPLETE ═══")
print(f"  Employees:      {db.query(Employee).filter(Employee.work_email != 'superadmin@reknew.ai').count()}")
print(f"  Departments:    {db.query(Department).count()}")
print(f"  Designations:   {db.query(Designation).count()}")
print(f"  Leave Types:    {db.query(LeaveType).count()}")
print(f"  Leave Balances: {db.query(LeaveBalance).count()}")
print(f"  Leave Requests: {db.query(LeaveRequest).count()}")
print(f"  Attendance:     {db.query(Attendance).count()}")
print(f"  Corrections:    {db.query(AttendanceCorrection).count()}")
print(f"  Trainings:      {db.query(Training).count()}")
print(f"  Enrollments:    {db.query(TrainingEnrollment).count()}")
print(f"  Projects:       {db.query(Project).count()}")
print(f"  Allocations:    {db.query(Allocation).count()}")
print(f"  Announcements:  {db.query(Announcement).count()}")
print(f"  Notifications:  {db.query(Notification).count()}")
print(f"  Channels:       {db.query(Channel).count()}")

db.close()
