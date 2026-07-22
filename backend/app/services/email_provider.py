"""Transactional email provider abstraction and Microsoft Graph implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from azure.identity import ClientSecretCredential, CertificateCredential, ManagedIdentityCredential

from app.core.config import settings


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    html_body: str
    text_body: str


class EmailProvider(ABC):
    @abstractmethod
    def send(self, message: EmailMessage) -> str | None:
        """Send a message and return a provider request/message identifier."""


class GraphEmailProvider(EmailProvider):
    """App-only Graph sender. Credentials never leave the backend process."""

    def __init__(self):
        mode = settings.GRAPH_AUTH_MODE.lower()
        if mode == "client_secret":
            if not all((settings.GRAPH_TENANT_ID, settings.GRAPH_CLIENT_ID, settings.GRAPH_CLIENT_SECRET)):
                raise RuntimeError("GRAPH_TENANT_ID, GRAPH_CLIENT_ID and GRAPH_CLIENT_SECRET are required")
            self.credential = ClientSecretCredential(
                settings.GRAPH_TENANT_ID, settings.GRAPH_CLIENT_ID, settings.GRAPH_CLIENT_SECRET
            )
        elif mode == "certificate":
            self.credential = CertificateCredential(
                settings.GRAPH_TENANT_ID,
                settings.GRAPH_CLIENT_ID,
                certificate_path=settings.GRAPH_CERTIFICATE_PATH,
                password=settings.GRAPH_CERTIFICATE_PASSWORD or None,
            )
        elif mode == "managed_identity":
            self.credential = ManagedIdentityCredential(
                client_id=settings.GRAPH_MANAGED_IDENTITY_CLIENT_ID or None
            )
        else:
            raise RuntimeError(f"Unsupported GRAPH_AUTH_MODE: {mode}")

    def send(self, message: EmailMessage) -> str | None:
        if not settings.TRANSACTIONAL_FROM_EMAIL:
            raise RuntimeError("TRANSACTIONAL_FROM_EMAIL is required")
        access_token = self.credential.get_token("https://graph.microsoft.com/.default").token
        sender = quote(settings.TRANSACTIONAL_FROM_EMAIL, safe="")
        response = httpx.post(
            f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={
                "message": {
                    "subject": message.subject,
                    "body": {"contentType": "HTML", "content": message.html_body},
                    "toRecipients": [{"emailAddress": {"address": message.to}}],
                },
                "saveToSentItems": True,
            },
            timeout=settings.GRAPH_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.headers.get("request-id") or response.headers.get("client-request-id")


def build_email_provider() -> EmailProvider:
    if settings.EMAIL_PROVIDER.lower() == "graph":
        return GraphEmailProvider()
    raise RuntimeError(f"Unsupported EMAIL_PROVIDER: {settings.EMAIL_PROVIDER}")
