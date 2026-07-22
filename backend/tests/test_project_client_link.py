from app.api.client_onboarding import ClientPayload
from app.models.operations import Project
from app.schemas.operations import ProjectCreate, ProjectUpdate


def test_project_schema_accepts_master_client_reference():
    payload = ProjectCreate(
        name="Client Portal",
        code="CP-001",
        client_id="client-123",
        client_name="Stale display value",
    ).model_dump()

    assert payload["client_id"] == "client-123"


def test_project_update_can_explicitly_switch_to_internal():
    payload = ProjectUpdate(client_id=None, client_name="Internal").model_dump(exclude_unset=True)

    assert payload == {"client_id": None, "client_name": "Internal"}


def test_project_model_has_client_foreign_key_column():
    column = Project.__table__.columns["client_id"]

    assert column.nullable is True
    assert {foreign_key.target_fullname for foreign_key in column.foreign_keys} == {"clients.id"}


def test_new_client_onboarding_defaults_to_contract_signed():
    payload = ClientPayload(
        client_name="Example Client",
        industry="Technology",
        primary_contact_name="Client Contact",
        contact_email="contact@example.com",
    )

    assert payload.status == "contract_signed"
