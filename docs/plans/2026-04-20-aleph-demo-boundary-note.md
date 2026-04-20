# Aleph Demo Boundary Note

- Date: `2026-04-20`
- Version: `day1-v0.1`
- Status: `boundary-definition`

## What Belongs in Aleph Core

The following belong in the framework:

- session model
- foreground ownership model
- client blueprint model
- runtime instance model
- memory layer model
- handoff mechanism
- stream event model
- runtime compilation pipeline
- adapter interfaces
- cache, prewarm, and telemetry hooks

These are reusable across multiple applications.

## What Belongs in a Hardware Interaction Demo

The following belong in a concrete demo app built on Aleph:

- hardware-specific event inputs
- device-side context mapping
- demo-specific client roster
- product-specific handoff policy
- demo-specific prompt tone and role semantics
- product service API
- UI and operator workflows

These are application choices, not framework invariants.

## What Must Stay Out of Core for Now

The following should not enter the framework core on Day 1:

- hardware SDK coupling
- world-model semantics
- device protocol contracts
- multimodal input assumptions
- app-specific memory meaning
- hardcoded product personas

## Practical Rule

If a feature only makes sense for the hardware interaction product, it should land in the demo layer first.

If the same feature would still make sense for a different Aleph application with different clients and no hardware semantics, it is a candidate for framework core.

## Day 2 Prerequisite

Only after these boundaries are accepted should Day 2 begin freezing service APIs or runtime integration contracts.

That keeps Aleph's framework surface stable before any product-facing service shape is locked in.
