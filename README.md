# Aleph

Aleph is an agent-infra orchestration framework for `multi-agent clients`.
Its job is not to replace a concrete agent runtime. Its job is to sit outside
those runtimes and make them easier to isolate, faster to respond, safer to
handoff, and simpler to configure at runtime.

In Aleph v1, `one client = one real AI agent`.

- A client is not a prompt fragment or a subagent slot.
- Each client owns private memory, runtime signals, and agent-native state.
- Shared memory is narrow, policy-governed, and explicitly written.
- Handoff is a first-class runtime mechanism.
- Aleph automatically compiles prompt, memory, tools, capability view, and
  handoff packet for the active client.

## Architecture

```text
                                 ALEPH

  Edge Gateway                    Aleph Cloud                     Agent Runtime Pool
  ---------------------------     -----------------------------   ------------------------
  Text / UI events           --->  SessionOrchestrator        ---> AgentAdapter(nanobot)
  Debounce / buffering             ProjectionCompiler         ---> AgentAdapter(mock)
  Stream rendering                 MemoryManager
                                   SwitchDaemon
                                   Cache / prewarm / trace

  Major functions by layer

  [Edge Gateway]
  - normalize incoming interaction events
  - keep the request path lightweight
  - consume stable presentation stream events

  [Aleph Cloud]
  - compile runtime projections for the active client
  - enforce private/shared/handoff memory boundaries
  - evaluate handoff rules and write handoff envelopes
  - maintain projection cache and memory slice cache
  - emit internal orchestration events and presentation stream events

  [Agent Runtime Pool]
  - run one real agent per client
  - receive compiled prompt/memory/tool surfaces via adapters
  - keep agent-native state behind an adapter boundary
```

### Layer notes

**Edge Gateway**

The edge side stays intentionally light. It gathers text or UI events, applies
small buffering/debounce behavior, and renders streaming output. It does not
own the heavy orchestration logic.

**Aleph Cloud**

This is the control plane. It contains:

- `ClientRegistry`
- `ProjectionCompiler`
- `MemoryManager`
- `SessionOrchestrator`
- `SwitchDaemon`

This layer takes design-time `ClientBlueprint`s and turns them into runtime
`ClientProjection`s.

**Agent Runtime Pool**

Every client maps to one real agent. Different runtimes can be attached through
adapters. In the current prototype:

- `NanobotAdapter` wraps local nanobot-style handlers
- `MockAgentAdapter` proves that a second runtime can be added without changing
  the orchestrator

## Core objects

- `ClientBlueprint`
  Design-time client definition: role, boundaries, declared capability,
  shared-memory policy, tools, handoff rules, runtime preferences.
- `ClientInstance`
  Runtime agent endpoint for a blueprint, with runtime signals and
  agent-native state.
- `ProjectionCompiler`
  Builds prompt, memory, tool, capability, and handoff projections.
- `HandoffEnvelope`
  Minimal packet passed to the next client during foreground transfer.
- `Presentation Stream Event`
  Stable public stream protocol with `status`, `delta`, `tool_event`,
  `handoff`, and `final`.

## Memory model

Aleph keeps memory boundaries at the framework layer:

- `private`
  Owned by one client only.
- `shared`
  Shared across clients, but only through explicit domain policy.
- `handoff`
  Used for client transfer and replay.
- `runtime`
  Logs, traces, and operational notes.
- `agent-native state`
  Maintained behind the adapter boundary. Aleph syncs it intentionally rather
  than treating it as the only source of truth.

## Runtime acceleration

Aleph is allowed to be internally complex as long as that complexity makes
client runtimes faster and cleaner.

Current v1 prototype includes:

- projection cache
- memory slice cache
- prompt skeleton reuse
- candidate client prewarm
- asynchronous memory-maintenance scheduling
- internal/presentation stream split

The key rule is that prewarm and preprocessing must stay:

- side-effect free
- cancelable
- budget-bounded per session

## What exists today

- Python-first v1 prototype
- SQLite-backed session state, memory, switch logs, caches, and prewarm jobs
- `SessionOrchestrator` for single-session, single-foreground operation
- policy-governed private/shared/handoff memory handling
- rule-based, explainable handoff
- streaming protocol with `status`, `delta`, `tool_event`, `handoff`, `final`
- `NanobotAdapter` plus a second `MockAgentAdapter`
- unit tests covering isolation, handoff, streaming, cache, and adapter
  extensibility

## Quick start

```bash
C:\Program Files\AutoClaw\resources\python\python.exe scripts\scenario.py
C:\Program Files\AutoClaw\resources\python\python.exe scripts\repl.py
C:\Program Files\AutoClaw\resources\python\python.exe scripts\run_tests.py
```

## Project docs

- [Changelog](CHANGELOG.md)
- [Aleph v1 plan](docs/plans/2026-04-18-aleph-mvp.md)
- [Client runtime design notes](docs/plans/2026-04-18-aleph-client-design.md)
- [Implementation summary and 7-day MVP delivery plan](docs/plans/2026-04-20-aleph-implementation-and-7day-plan.md)
- [Day 1 framework overview](docs/plans/2026-04-20-aleph-framework-overview.md)
- [Day 1 core architecture](docs/plans/2026-04-20-aleph-core-architecture.md)
- [Day 1 public schema draft](docs/plans/2026-04-20-aleph-public-schema-draft.md)
- [Day 1 demo boundary note](docs/plans/2026-04-20-aleph-demo-boundary-note.md)

## Roadmap

- `ExternalStateAdapter` for future device/environment integration
- multimodal edge events
- richer routing and scheduling policies
- more agent runtime adapters
- deeper agent-native state synchronization
- a trimmed edge-side Aleph runtime when the cloud control plane is stable
