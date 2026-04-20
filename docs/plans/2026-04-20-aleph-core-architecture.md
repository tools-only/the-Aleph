# Aleph Core Architecture

- Date: `2026-04-20`
- Version: `day1-v0.1`
- Status: `architecture-outline`

## Layer Model

### Core Domain Layer

This layer defines Aleph's stable concepts and invariants.

Core objects:

- `AppSpec`
- `ClientBlueprint`
- `ClientInstance`
- `Session`
- `Turn`
- `MemoryRecord`
- `HandoffEnvelope`
- `StreamEvent`
- `RuntimeSignal`

This layer contains no hardware-specific semantics.

### Runtime Control Layer

This layer runs the session and client lifecycle.

Primary modules:

- `SessionManager`
- `ForegroundController`
- `ProjectionCompiler`
- `MemoryManager`
- `HandoffEngine`
- `StreamEmitter`
- `RuntimeSignalCollector`

Responsibilities:

- maintain one foreground client per session
- dispatch turns
- compile runtime projections
- persist and read framework memory layers
- execute handoff
- emit standard stream events

### Adapter Layer

This layer keeps Aleph adaptable to external runtimes and infrastructure.

Primary extension points:

- `AgentRuntimeAdapter`
- `MemoryBackendAdapter`
- `ToolSurfaceAdapter`
- `ExternalContextAdapter`
- `PersistenceAdapter`
- `TelemetryAdapter`

Adapters should absorb integration-specific logic so the core model remains stable.

### Application / Demo Layer

This layer contains concrete products built on Aleph.

Examples:

- hardware interaction demo
- alternate agent products with different client sets

This layer may define:

- concrete client blueprints
- app-specific policies
- external context mappings
- product service APIs
- demo UI

## Runtime Chain

The framework-level runtime chain should be understood as:

1. Application registers an `AppSpec` and a set of `ClientBlueprint`s.
2. Aleph creates or resumes a `Session`.
3. A `Turn` is submitted to the active session.
4. The foreground client is resolved.
5. `ProjectionCompiler` builds prompt, memory, tool, capability, and handoff projections.
6. `AgentRuntimeAdapter` executes the client turn.
7. `MemoryManager` persists private/shared/handoff/runtime records.
8. `HandoffEngine` may switch the foreground client.
9. `StreamEmitter` produces standard `StreamEvent`s.
10. `RuntimeSignalCollector` updates runtime signals for observation and future routing.

## Core Invariants

- Every client maps to one real AI agent.
- Every session has one foreground client at a time.
- Shared memory is policy-governed.
- Handoff must produce an explicit handoff artifact.
- Runtime signals are separate from declared capability.
- Demo-specific context must enter through adapters or app policies, not through core object mutation.
