# Aleph Public Schema Draft

- Date: `2026-04-20`
- Version: `day1-v0.1`
- Status: `schema-draft`

## AppSpec

Purpose: define one Aleph application assembly.

Suggested fields:

- `id`
- `name`
- `client_blueprints`
- `adapter_bindings`
- `memory_backend`
- `persistence_backend`
- `telemetry_backend`
- `policies`
- `metadata`

## ClientBlueprint

Purpose: design-time client definition.

Required fields:

- `id`
- `display_name`
- `role`
- `system_prompt`
- `adapter_kind`
- `boundaries`
- `declared_capability`
- `shared_memory_policy`
- `tools`
- `handoff_rules`
- `runtime_preferences`

Suggested shape:

- `declared_capability`
  - `domains`
  - `permissions`
  - `handoff_keywords`
- `shared_memory_policy`
  - `read_domains`
  - `write_domains`
  - `allowed_kinds`
  - `write_mode`
- `runtime_preferences`
  - `transcript_window`
  - `private_memory_window`
  - `shared_memory_window`
  - `handoff_window`
  - `stream_mode`

## ClientInstance

Purpose: runtime representation of a client.

Suggested fields:

- `id`
- `blueprint_id`
- `adapter_kind`
- `status`
- `runtime_signals`
- `agent_native_state`
- `metadata`

## Session

Purpose: top-level runtime container for a conversation or task thread.

Suggested fields:

- `id`
- `title`
- `status`
- `foreground_client_id`
- `foreground_reason`
- `memory_epoch`
- `tool_epoch`
- `policy_epoch`
- `metadata`
- `created_at`
- `updated_at`

## Turn

Purpose: one input/output cycle within a session.

Suggested fields:

- `id`
- `session_id`
- `client_id`
- `role`
- `content`
- `visibility`
- `source_event_id`
- `metadata`
- `created_at`

## MemoryRecord

Purpose: framework-managed memory entry.

Suggested fields:

- `id`
- `session_id`
- `layer`
- `owner_client_id`
- `domain`
- `kind`
- `content`
- `write_mode`
- `metadata`
- `created_at`
- `updated_at`

Allowed framework layers:

- `private`
- `shared`
- `handoff`
- `runtime`

## HandoffEnvelope

Purpose: explicit transfer artifact between clients.

Suggested fields:

- `from_client_id`
- `to_client_id`
- `reason`
- `explanation`
- `summary`
- `shared_context_refs`
- `created_at`

## StreamEvent

Purpose: standard runtime event emitted by Aleph.

Suggested fields:

- `event_kind`
- `source`
- `created_at`
- `payload`

Minimum framework event kinds:

- `status`
- `delta`
- `tool_event`
- `handoff`
- `final`

## RuntimeSignal

Purpose: observed runtime state, not design-time capability.

Suggested fields:

- `last_latency_ms`
- `last_success`
- `health`
- `recent_tool_status`
- `failure_count`
- `updated_at`
