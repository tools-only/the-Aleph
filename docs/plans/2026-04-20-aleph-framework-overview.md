# Aleph Framework Overview

- Date: `2026-04-20`
- Version: `day1-v0.1`
- Status: `framework-definition`

## What Aleph Is

Aleph is a `multi-client agent orchestration framework`.

Its job is to provide the runtime structure for:

- client declaration and registration
- session lifecycle management
- private/shared/handoff memory boundaries
- handoff between clients
- runtime compilation of prompt, memory, tools, capability, and handoff context
- standard stream output
- adapter-based extensibility

Aleph is a framework first. It is not defined by any single product demo.

## What Aleph Is Not

Aleph is not:

- a hardware product by itself
- a fixed world-model engine
- a device protocol standard
- a UI framework
- a single agent runtime replacement
- a prompt-only subagent manager

Aleph should not bake one specific hardware scenario into its core model.

## Core Design Principles

- `one client = one real AI agent`
- `one session = one active foreground client at a time`
- memory boundaries are framework-level constraints, not app-specific conventions
- handoff is a framework capability, but handoff policy can be app-defined
- adapters are first-class extension points
- demo-specific semantics belong outside the framework core

## Aleph and Demo Applications

Aleph should sit below applications.

- `Aleph framework`
  Defines the common runtime model and extension points.
- `Demo application`
  Uses Aleph to assemble a concrete product, such as a hardware-interaction app.

The demo should configure Aleph rather than redefine it.

## Day 1 Outcome

Day 1 only freezes framework-level concepts:

- framework positioning
- framework layers
- framework objects
- framework extension points
- framework vs demo boundaries

Day 1 does not freeze:

- hardware interaction logic
- device-side contracts
- product UI
- demo-specific handoff strategies
