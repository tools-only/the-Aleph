from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MemoryBackendAdapter(ABC):
    kind = "memory-backend"

    @abstractmethod
    def save_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_records(self, filter_payload: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError


class ToolSurfaceAdapter(ABC):
    kind = "tool-surface"

    @abstractmethod
    def build_surface(self, *, client: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class ExternalContextAdapter(ABC):
    kind = "external-context"

    @abstractmethod
    def load_context(self, *, session: dict[str, Any], user_input: str) -> dict[str, Any]:
        raise NotImplementedError


class PersistenceAdapter(ABC):
    kind = "persistence"

    @abstractmethod
    def save_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_memory(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class TelemetryAdapter(ABC):
    kind = "telemetry"

    @abstractmethod
    def record_signal(self, *, client_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def record_stream_event(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError
