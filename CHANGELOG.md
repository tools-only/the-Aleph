# Changelog

All notable changes to Aleph are documented in this file.

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
