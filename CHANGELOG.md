# Changelog

All notable changes to Aleph are documented in this file.

## v0.1.5 - 2026-04-21

### Summary

This version adds Stage 2 audio integration foundations for embedded devices (e.g., esp-brookesia). New `AlephAudioAdapter` provides ASR (speech-to-text) and TTS (text-to-speech) abstraction, enabling device clients to stream audio via WebSocket instead of text. The adapter bridges device audio frames ↔ Aleph session orchestration, with pluggable ASR/TTS service interfaces for cloud-based or local deployment. WebSocket endpoint follows the Stage 2 bidirectional audio protocol.

### Added

- Added `aleph/adapters/audio_adapter.py`: `AlephAudioAdapter` class for device audio ↔ Aleph session bridging.
  - `ASRService` (ABC): Speech-to-text abstraction with `MockASRService` implementation.
  - `TTSService` (ABC): Text-to-speech abstraction with `MockTTSService` implementation.
  - `AudioFrame`, `AudioCodec`: Data models for audio frames (OPUS 16kHz, 24kbps).
  - `process_audio_stream()`: Async generator that consumes device audio, performs ASR, routes to Aleph, yields TTS response.
- Added WebSocket endpoint `POST /sessions/{session_id}/audio` in `aleph/service/api.py`:
  - Binary frame protocol: device sends OPUS frames with metadata, receives TTS audio.
  - Supports concurrent audio streaming for real-time voice interaction.
  - Handles connection lifecycle, silence detection, and error recovery (TODOs for production).
- Exported new adapter classes from `aleph/adapters/__init__.py`.

### Notes

- **MVP Scope**: ASR/TTS services are abstracted but default to mock implementations (return fixed text/silence).
  - TODO: Integrate real services (Google Cloud Speech, Whisper, TTS, etc.) per deployment needs.
- **Silence Detection**: Basic buffer-size heuristic for MVP; production should use RMS-based voice activity detection.
- **Device Integration**: Target pattern is `brookesia_agent_aleph` (separate C++ component repo) consuming Aleph via this adapter.
  - See `docs/plans/2026-04-21-brookesia-aleph-integration.md` for esp-brookesia integration guide.

## v0.1.4 - 2026-04-21

### Summary

This version adds a scripted mock pipeline that developers can use to validate Aleph's event channel end-to-end without plugging in a real LLM or nanobot agent. Three pre-built mock agents (alpha/beta/gamma) exercise every event type (`status`, `delta`, `tool_event`, `handoff`, `final`), every memory layer (private/shared/handoff), and the full handoff chain. All additions are opt-in; no framework source file is modified.

### Added

- Added `aleph/mocks/` module with `make_scripted_handler(engine, scenarios_spec)` factory and `load_scenarios(path)` loader.
- Added three scenario JSON files under `configs/mocks/`:
  - `mock_alpha.json` (memory-heavy archivist, Iris-analog)
  - `mock_beta.json` (execution operator, Sol-analog)
  - `mock_gamma.json` (relational mediator, Mire-analog)
- Added `configs/clients/mock_pipeline.clients.json`: blueprints for the three mock clients.
- Added `scripts/run_mock_api.py`: launcher that registers mock clients with scripted handlers and serves the FastAPI app on `127.0.0.1:8000`.
- Added `docs/plans/2026-04-20-aleph-mock-pipeline-guide.md`: usage guide covering scenario shape, keyword triggers, handoff chain verification, and how the mock interacts with v0.1.3 real-time streaming.

### Notes

- Scripted handlers exploit the v0.1.3 `SessionEventBus` to emit intermediate events (from inside the BackgroundTask thread) that flow to SSE clients in real time with configurable delays between steps.
- Scenario `steps[]` (emitted live) and `result{}` (returned to orchestrator) are separate; putting `tool_events` in both would duplicate them on the stream.

## v0.1.3 - 2026-04-20

### Summary

This version replaces SQLite-polling-based SSE with a real-time in-memory event bus, and makes turn processing non-blocking at the HTTP layer. Events now flow to connected SSE clients immediately as the handler executes, without waiting for the full turn to complete.

### Added

- Added `SessionEventBus` (`aleph/core/event_bus.py`): per-session `asyncio.Queue` broker for real-time presentation event delivery.
- Added nanobot adaptation guide (`docs/plans/2026-04-20-aleph-nanobot-adaptation-guide.md`): step-by-step integration guide for wrapping an existing nanobot agent as an Aleph handler.

### Changed

- `StreamEmitter` now accepts an optional `event_bus` parameter and publishes every presentation event to the session's live queue in addition to SQLite persistence.
- `AlephEngine` composes a `SessionEventBus` instance and wires it into `StreamEmitter`.
- `POST /sessions/{id}/turns` now returns `202 Accepted` immediately and runs the turn as a FastAPI `BackgroundTask`, enabling concurrent SSE streaming.
- `GET /sessions/{id}/stream` now subscribes to the in-memory queue instead of polling SQLite every 500 ms; sends SSE keepalive comments on 30-second idle intervals; cleans up the queue on client disconnect.
- Updated `aleph/core/__init__.py` to export `SessionEventBus`.

### Verified

- Existing test suite (`scripts/run_tests.py`) passes without modification.
- Manual SSE test: open stream before submitting a turn → events appear in the SSE terminal before the background task completes.

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
