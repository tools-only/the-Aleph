from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class AppSpec:
    id: str
    name: str
    client_blueprints: list[dict] = field(default_factory=list)
    adapter_bindings: dict[str, str] = field(default_factory=dict)
    memory_backend: str = "sqlite"
    persistence_backend: str = "sqlite"
    telemetry_backend: str = "runtime-signals"
    policies: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ClientBlueprint:
    id: str
    display_name: str
    role: str
    system_prompt: str
    adapter_kind: str
    boundaries: list[str] = field(default_factory=list)
    declared_capability: dict[str, Any] = field(default_factory=dict)
    shared_memory_policy: dict[str, Any] = field(default_factory=dict)
    tools: list[dict[str, Any]] = field(default_factory=list)
    handoff_rules: dict[str, Any] = field(default_factory=dict)
    runtime_preferences: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RuntimeSignal:
    last_latency_ms: float | None = None
    last_success: bool | None = None
    health: str = "unknown"
    recent_tool_status: dict[str, Any] = field(default_factory=dict)
    failure_count: int = 0
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ClientInstance:
    id: str
    blueprint_id: str
    adapter_kind: str
    status: str = "ready"
    runtime_signals: dict[str, Any] = field(default_factory=dict)
    agent_native_state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Session:
    id: str
    title: str
    status: str
    foreground_client_id: str
    foreground_reason: str
    memory_epoch: int
    tool_epoch: int
    policy_epoch: int
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Turn:
    id: str
    session_id: str
    client_id: str | None
    role: str
    content: str
    visibility: str
    source_event_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MemoryRecord:
    id: str
    session_id: str
    layer: str
    owner_client_id: str | None
    domain: str | None
    kind: str
    content: str
    write_mode: str = "append"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HandoffEnvelope:
    from_client_id: str
    to_client_id: str
    reason: str
    explanation: str
    summary: str
    shared_context_refs: list[str] = field(default_factory=list)
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StreamEvent:
    event_kind: str
    source: str
    created_at: str | None
    payload: dict[str, Any] = field(default_factory=dict)
    channel: str = "presentation"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
