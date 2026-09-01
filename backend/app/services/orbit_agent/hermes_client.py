from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are Orbit AI, the assistant inside the ReKnew Employee Management System.

You may help with general employee-management questions.

Only claim that you can access or perform an EMS capability when an approved backend tool for that capability is actually available.

Do not fabricate employee, leave, attendance, timesheet, allocation, or company data.

If the user asks for real company data and no approved tool is available, clearly explain that the capability has not been connected yet.
"""


class HermesClientError(Exception):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(slots=True)
class HermesClient:
    api_url: str
    api_key: str
    timeout_seconds: float

    async def chat(
        self,
        message: str,
        *,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        api_url = self.api_url.strip().rstrip("/")
        api_key = self.api_key.strip()
        if not api_url or not api_key:
            raise HermesClientError(
                "Orbit AI is not configured right now.",
                status_code=503,
            )

        payload = {
            "model": "hermes-agent",
            "messages": [{"role": "system", "content": _SYSTEM_PROMPT}],
            "stream": False,
        }
        if history:
            payload["messages"].extend(
                {
                    "role": item["role"],
                    "content": item["content"],
                }
                for item in history
                if item.get("role") in {"user", "assistant"} and item.get("content", "").strip()
            )
        payload["messages"].append({"role": "user", "content": message})

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{api_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            logger.warning("Hermes request timed out.")
            raise HermesClientError(
                "Orbit AI timed out. Please try again.",
                status_code=504,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Hermes transport failure: %s", exc.__class__.__name__)
            raise HermesClientError(
                "Orbit AI is unavailable right now. Please try again later.",
                status_code=503,
            ) from exc

        if response.status_code in {401, 403}:
            logger.error("Hermes rejected the configured credential.")
            raise HermesClientError(
                "Orbit AI is unavailable right now. Please try again later.",
                status_code=503,
            )
        if response.status_code >= 400:
            logger.warning("Hermes returned HTTP %s.", response.status_code)
            raise HermesClientError(
                "Orbit AI could not answer right now. Please try again later.",
                status_code=502,
            )

        try:
            body = response.json()
            choices = body["choices"]
            assistant_content = choices[0]["message"]["content"].strip()
        except (KeyError, IndexError, AttributeError, TypeError, ValueError) as exc:
            logger.warning("Hermes response shape was invalid.")
            raise HermesClientError(
                "Orbit AI returned an invalid response. Please try again later.",
                status_code=502,
            ) from exc

        if not assistant_content:
            logger.warning("Hermes response did not include assistant content.")
            raise HermesClientError(
                "Orbit AI returned an invalid response. Please try again later.",
                status_code=502,
            )
        return assistant_content

    async def health(self) -> dict | None:
        api_url = self.api_url.strip().rstrip("/")
        if not api_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=min(self.timeout_seconds, 5.0)) as client:
                response = await client.get(api_url.replace("/v1", "") + "/health")
            if response.status_code >= 400:
                return None
            body = response.json()
            if not isinstance(body, dict):
                return None
            return body
        except (httpx.HTTPError, ValueError, TypeError):
            return None


def get_hermes_client() -> HermesClient:
    return HermesClient(
        api_url=settings.HERMES_API_URL,
        api_key=settings.HERMES_API_KEY,
        timeout_seconds=settings.AI_CHAT_TIMEOUT_SECONDS,
    )
