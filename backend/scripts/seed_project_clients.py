"""Idempotently create client records for legacy external project names and link them."""

from __future__ import annotations

import re

from sqlalchemy import func

from app.api.client_onboarding import ensure_defaults
from app.core.database import SessionLocal, ensure_project_workflow_tables
from app.models.client_onboarding import Client, ClientActivityLog, ClientOnboarding
from app.models.employee import Employee
from app.models.operations import Project


INTERNAL_CLIENT_NAMES = {"", "internal", "reknew", "reknew orbit"}


def placeholder_email(client_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", client_name.lower()).strip("-") or "client"
    return f"onboarding+{slug}@example.com"


def seed() -> tuple[int, int]:
    ensure_project_workflow_tables()
    db = SessionLocal()
    created_clients = 0
    linked_projects = 0
    try:
        actor = db.query(Employee).filter(func.lower(Employee.work_email) == "superadmin@reknew.ai").first()
        projects = db.query(Project).filter(Project.client_id.is_(None)).all()
        for project in projects:
            legacy_name = (project.client_name or "").strip()
            if legacy_name.lower() in INTERNAL_CLIENT_NAMES:
                project.client_id = None
                project.client_name = "Internal"
                continue

            client = db.query(Client).filter(func.lower(Client.client_name) == legacy_name.lower()).first()
            if not client:
                client = Client(
                    client_name=legacy_name,
                    industry="To be confirmed",
                    primary_contact_name="To be confirmed",
                    contact_email=placeholder_email(legacy_name),
                    contract_start_date=project.start_date,
                    contract_end_date=project.end_date,
                    status="onboarding",
                    owner_id=project.created_by or (actor.id if actor else None),
                    notes=f"Created from legacy project {project.code}. Replace placeholder contact details during onboarding review.",
                    created_by=actor.id if actor else project.created_by,
                    updated_by=actor.id if actor else project.created_by,
                )
                db.add(client)
                db.flush()
                created_clients += 1

            onboarding = db.query(ClientOnboarding).filter(ClientOnboarding.client_id == client.id).first()
            if not onboarding:
                onboarding = ClientOnboarding(
                    client_id=client.id,
                    stage="Team Allocation" if project.status == "active" else "Contract Signed",
                    target_go_live_date=project.end_date,
                    owner_id=client.owner_id,
                    created_by=actor.id if actor else project.created_by,
                    updated_by=actor.id if actor else project.created_by,
                )
                db.add(onboarding)
                db.add(ClientActivityLog(
                    client_id=client.id,
                    action="Imported from project",
                    details=f"Linked legacy project {project.name} ({project.code}).",
                    performed_by=actor.id if actor else project.created_by,
                    created_by=actor.id if actor else project.created_by,
                    updated_by=actor.id if actor else project.created_by,
                ))

            project.client_id = client.id
            project.client_name = client.client_name
            linked_projects += 1
            if actor:
                ensure_defaults(db, client.id, actor)

        db.commit()
        return created_clients, linked_projects
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    created, linked = seed()
    print(f"Created {created} client(s); linked {linked} project(s).")
