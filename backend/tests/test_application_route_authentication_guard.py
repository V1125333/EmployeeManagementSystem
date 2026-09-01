from fastapi.routing import APIRoute

from app.core.authentication import (
    get_authenticated_actor,
    get_authenticated_employee,
    get_authenticated_principal,
    get_password_change_actor,
)
from app.main import app


PUBLIC_API_OPERATIONS = {
    ("POST", "/api/v1/auth/check-email"),
    ("POST", "/api/v1/auth/verify-setup-code"),
    ("POST", "/api/v1/auth/set-password"),
    ("POST", "/api/v1/auth/confirm-totp"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/login/verify-password"),
    ("POST", "/api/v1/auth/login/verify-mfa"),
    ("POST", "/api/v1/auth/forgot-password"),
    ("POST", "/api/v1/auth/forgot-password/initiate"),
    ("POST", "/api/v1/auth/forgot-password/verify-mfa"),
    ("POST", "/api/v1/auth/forgot-password/reset"),
    ("POST", "/api/v1/auth/request-unlock"),
    ("GET", "/api/v1/auth/me/{email}"),
    ("GET", "/api/v1/certificates/verify/{cert_id}"),
}

APPROVED_AUTH_DEPENDENCIES = {
    get_authenticated_actor,
    get_authenticated_principal,
    get_authenticated_employee,
    get_password_change_actor,
}


def _dependency_calls(route: APIRoute):
    pending = list(route.dependant.dependencies)
    while pending:
        dependency = pending.pop()
        yield dependency.call
        pending.extend(dependency.dependencies)


def test_every_api_operation_is_authenticated_or_explicitly_public():
    actual_public = set()
    missing_authentication = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/v1"):
            continue
        dependencies = set(_dependency_calls(route))
        for method in route.methods:
            operation = (method, route.path)
            if operation in PUBLIC_API_OPERATIONS:
                actual_public.add(operation)
            elif not dependencies.intersection(APPROVED_AUTH_DEPENDENCIES):
                missing_authentication.append(operation)

    assert not missing_authentication
    assert actual_public == PUBLIC_API_OPERATIONS
    assert not any(path.startswith("/api/v1/dashboard") for _, path in PUBLIC_API_OPERATIONS)
