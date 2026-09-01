"""Immutable, explicit capability registry for Platform v1."""

from __future__ import annotations

from types import MappingProxyType

from app.ai_platform.capability import CapabilityDefinition
from app.ai_platform.contracts import Availability
from app.ai_platform.errors import (
    DisabledCapabilityError,
    DuplicateCapabilityError,
    ShadowOnlyCapabilityError,
    UnknownCapabilityError,
)


class CapabilityRegistry:
    """A construction-time registry with no post-initialization mutation API."""

    __slots__ = ("_definitions", "_versions", "_sealed")

    def __init__(self, definitions: tuple[CapabilityDefinition, ...] = ()):
        entries: dict[tuple[str, int], CapabilityDefinition] = {}
        versions: dict[str, list[int]] = {}
        for definition in definitions:
            if not isinstance(definition, CapabilityDefinition):
                raise TypeError("registry entries must be explicit CapabilityDefinition objects")
            if definition.key in entries:
                raise DuplicateCapabilityError("A capability version was registered more than once.")
            entries[definition.key] = definition
            versions.setdefault(definition.capability_id, []).append(definition.version)
        object.__setattr__(self, "_definitions", MappingProxyType(entries))
        object.__setattr__(
            self,
            "_versions",
            MappingProxyType({key: tuple(sorted(value)) for key, value in versions.items()}),
        )
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_sealed", False):
            raise AttributeError("CapabilityRegistry is immutable")
        object.__setattr__(self, name, value)

    def get(self, capability_id: str, version: int) -> CapabilityDefinition:
        try:
            return self._definitions[(capability_id, version)]
        except KeyError as exc:
            raise UnknownCapabilityError("The requested capability or version is not registered.") from exc

    def resolve(self, capability_id: str, version: int | None = None, *, production: bool = True) -> CapabilityDefinition:
        if version is None:
            registered = self._versions.get(capability_id)
            if not registered:
                raise UnknownCapabilityError("The requested capability is not registered.")
            version = registered[-1]
        definition = self.get(capability_id, version)
        if definition.kill_switch_active or definition.availability is Availability.DISABLED:
            raise DisabledCapabilityError("The requested capability is currently unavailable.")
        if production and definition.availability is Availability.SHADOW_ONLY:
            raise ShadowOnlyCapabilityError("The requested capability is not available for production execution.")
        return definition

    def list_metadata(self, *, limit: int = 100) -> tuple[tuple[str, int, Availability], ...]:
        bounded = max(0, min(limit, 100))
        ordered = sorted(self._definitions.values(), key=lambda item: item.key)
        return tuple((item.capability_id, item.version, item.availability) for item in ordered[:bounded])

    def is_available(self, capability_id: str, version: int, *, production: bool = True) -> bool:
        try:
            self.resolve(capability_id, version, production=production)
            return True
        except (UnknownCapabilityError, DisabledCapabilityError, ShadowOnlyCapabilityError):
            return False

    def is_read_only(self, capability_id: str, version: int) -> bool:
        return self.get(capability_id, version).is_read_only

    def __len__(self) -> int:
        return len(self._definitions)
