# Changelog

All notable changes to Aleph are documented in this file.

## v0.1.2 - 2026-04-20

### Summary

This version adds the first minimal cloud-service foundations around the Python Aleph framework.
The core runtime is still adapter-driven, but Aleph can now expose a cleaner service boundary for multi-session orchestration, session inspection, and stream consumption before wiring in real agent runtimes.

### Added

- Added multi-session management primitives:
  - explicit session creation
  - session listing
  - session state lookup
- Added config-driven client registration:
  - JSON client blueprint loading
  - YAML client blueprint loading
  - engine-side registration helper
- Added initial service-layer package:
  - FastAPI app factory
  - request logging
  - runtime error handling
  - session-oriented HTTP endpoints
  - SSE-style session stream endpoint
- Added sample client blueprint config under `configs/clients/demo.clients.json`.
- Added service foundation tests covering:
  - multi-session creation and listing
  - event cursor queries
  - config-based client loading

### Changed

- Extended `SqliteStore` with:
  - session listing support
  - cursor-style session event querying for streaming consumers
- Extended `ClientSessionManager` and `AlephEngine` with service-friendly session APIs.
- Updated the public package exports to expose:
  - config loader helpers
  - service app factory
- Updated `README.md` with a minimal service-layer section and API entrypoints.
- Added optional `service` dependencies in `pyproject.toml` for:
  - `fastapi`
  - `uvicorn`
  - `pyyaml`

### Verified

- Ran the full Python test suite successfully:
  - `scripts/run_tests.py`

## v0.1.1 - 2026-04-20

### Summary

This version turns the Day 1 framework design into actual Python framework code.
Aleph is now more clearly expressed as an independent multi-client agent orchestration framework, rather than only a runtime prototype plus design notes.

### Added

- Added framework domain models for:
  - `AppSpec`
  - `ClientBlueprint`
  - `ClientInstance`
  - `Session`
  - `Turn`
  - `MemoryRecord`
  - `HandoffEnvelope`
  - `StreamEvent`
  - `RuntimeSignal`
- Added adapter-side extension interfaces for:
  - `MemoryBackendAdapter`
  - `ToolSurfaceAdapter`
  - `ExternalContextAdapter`
  - `PersistenceAdapter`
  - `TelemetryAdapter`
- Added runtime control components for:
  - `ForegroundController`
  - `HandoffEngine`
  - `StreamEmitter`
  - `RuntimeSignalCollector`
- Added Day 1 framework design documents:
  - framework overview
  - core architecture
  - public schema draft
  - demo boundary note
- Added framework abstraction tests.

### Changed

- Refactored `AlephEngine` to assemble the new framework-level control components.
- Refactored `SessionOrchestrator` to delegate:
  - foreground ownership
  - handoff execution
  - stream emission
  - runtime signal updates
- Updated package exports so Day 1 framework abstractions are importable from the public package surface.
- Updated `README.md` so Day 1 framework design documents are discoverable from the main project entry point.

### Verified

- Ran the full Python test suite successfully:
  - `scripts/run_tests.py`
- Verified existing orchestration behaviors still hold:
  - private/shared memory isolation
  - rule-based handoff
  - stream protocol output
  - cache and prewarm behavior
  - adapter extensibility

## v0.1.0 - 2026-04-19

### Summary

Initial Python-first Aleph prototype centered on client runtime orchestration.

### Included

- SQLite-backed runtime state
- session and client orchestration prototype
- projection compiler and memory manager prototype
- nanobot/mock adapters
- basic README and design plan set
