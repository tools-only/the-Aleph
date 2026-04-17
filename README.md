# Aleph

Aleph is a chat-first MVP for a multi-persona product where several persona sessions
share one continuous reality without sharing the same inner world.

## Product view

Aleph is not a generic multi-agent collaboration board. It is a product about
multiple personas inhabiting one continuous reality.

- Reality keeps moving forward even when the foreground persona changes
- Each persona owns a private inner world: memory, voice, interpretation, and judgment
- Shared memory is intentionally narrow and only preserves the minimum common ground
- A switch is meaningful because the next persona inherits unresolved consequences
- The product is designed to preserve tension, continuity, and interpretive difference

## Design panorama

```text
                          ALEPH

    User / external world events
                |
                v
    +---------------------------+
    |       Reality Layer       |
    |---------------------------|
    | RealityThread             |
    | Consequences              |
    | Open loops                |
    | Recent reality events     |
    +---------------------------+
                |
                v
    +---------------------------+
    |      Orchestration        |
    |---------------------------|
    | ForegroundControl         |
    | SwitchDaemon              |
    | Handoff summary           |
    | Switch log                |
    +---------------------------+
         |                 |
         v                 v
  +-------------+   +-------------+   +-------------+
  | Persona A   |   | Persona B   |   | Persona C   |
  |-------------|   |-------------|   |-------------|
  | Private mem |   | Private mem |   | Private mem |
  | Voice       |   | Voice       |   | Voice       |
  | Lens        |   | Lens        |   | Lens        |
  +-------------+   +-------------+   +-------------+
         \                 |                 /
          \                |                /
           +--------------------------------+
           |      SharedMemoryDomain        |
           | commitments / social / facts   |
           +--------------------------------+
```

## Core model

### Reality Layer

This is the product's source of continuity. It stores what is still true in the
world, what remains unresolved, and which consequences are still alive.

- `RealityThread` is the single continuous reality, not a chat transcript
- `Consequence` is an abstract inheritable effect, not a hardcoded pain model
- `open loops` track commitments, risks, relationship residue, and unfinished threads

### Persona Layer

Each persona is a distinct session container rather than a simple routing target.

- `PersonaProfile` defines style, specialties, boundaries, and shared-memory access
- `private memory` stores how that persona interprets the world
- personas do not automatically gain access to each other's inner narrative

### Orchestration Layer

This layer makes switching legible and safe.

- `ForegroundControl` guarantees one foreground persona at a time
- `SwitchDaemon` handles manual and semi-automatic handoff
- every switch produces an explanation and a handoff summary
- the next persona inherits the reality state rather than starting fresh

## What exists

- A continuous `RealityThread` with active consequences and open loops
- Persona sessions with private memory and limited shared memory
- A `SwitchDaemon` that handles manual and semi-automatic handoff
- A runnable CLI prototype and scripted scenario
- Tests for continuity, privacy, shared memory, and switch explanation

## Quick start

```bash
node src/demo/scenario.js
node src/demo/repl.js
npm.cmd test
```

## CLI commands

- `/personas` list available personas
- `/switch <persona-id>` manually switch foreground persona
- `/state` inspect current reality, consequences, and recent switch log
- `/quit` exit the REPL

## Plan doc

The product design plan lives at:

`docs/plans/2026-04-18-aleph-mvp.md`

## Roadmap

### Current MVP

- chat-first prototype
- SQLite-backed truth store plus JSONL debug logs
- single foreground persona model
- semi-automatic switching with explanations
- private memory, shared memory, and reality state separation

### Next updates

- add a small web UI with panes for current persona, live consequences, and recent switches
- move personas into editable config files so tone, specialties, and shared domains are easy to tune
- improve consequence lifecycle so items can escalate, cool down, merge, or be resolved more naturally
- add richer handoff summaries that preserve continuity without flattening persona differences
- add scenario packs for different use cases without hardcoding domain-specific state into the core model

### Later product evolution

- support background observer personas without allowing multi-foreground contention
- add richer narrative and relational state visualizations
- explore stronger memory retrieval and long-horizon continuity
- integrate external systems only after the chat-first product loop feels strong on its own
