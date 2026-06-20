# Python Queued Message Handler Architecture

This repository follows the Python Queued Message Handler architecture (QMH).

## Core Model

- Build the application as a set of independent modules.
- Each module owns its own behavior and typically runs in its own thread or execution loop.
- Modules must not call each other directly for normal coordination.
- Cross-module coordination happens by sending messages through the protocol.

## The Protocol

The protocol is the messaging backbone for the application.

- It acts as the message bus between the main application and all modules.
- Modules register with the protocol at startup and receive or expose an address.
- Messages are routed by module address rather than by direct object reference.
- A typical action message contains a destination address, a command name, and an optional payload.
- Message delivery is queue-based, so modules can process work asynchronously and remain decoupled from each other.

When editing or generating code, preserve these constraints:

- Prefer `protocol.send_action(...)` or the local project equivalent over direct module-to-module method calls.
- Keep message payloads explicit and serializable where practical.
- Treat the protocol as the single coordination boundary between modules.
- Do not introduce shared-control flows that bypass the message queue unless the existing architecture already requires it.

## What a Module Is

A module is a self-contained unit of application behavior that communicates through the protocol.

- A module should have one clear responsibility.
- A module handles incoming commands or messages and performs background work relevant to that responsibility.
- A module should encapsulate its own internal state instead of exposing implementation details to peer modules.
- New behavior should usually be added by extending a module's handled commands or by introducing a new module, not by tightly coupling existing modules together.

## Standard vs Factory Modules

There are two supported module shapes.

### Standard module

Use a standard module when there is a single implementation.

- It extends the base module type directly.
- It contains the concrete runtime behavior in one class.
- It is the default choice for straightforward features.

Typical use cases:

- Logging
- Simple device control
- A single UI integration
- One-off coordination logic

### Factory module

Use a factory module when multiple interchangeable implementations are expected.

- It defines a `Base<Name>` abstract interface or abstract base class.
- Concrete implementations provide the real behavior behind that interface.
- Implementations are selected through a factory or registration mechanism rather than hard-coded branching across the app.
- This pattern is useful when the project needs simulated, hardware, mock, or environment-specific variants.

Typical use cases:

- Simulated vs real hardware integrations
- Test doubles for external systems
- Platform-specific backends

When generating a factory module, keep the abstraction boundary clean:

- Put shared contract methods on the base class.
- Keep implementation-specific details inside each concrete implementation.
- Register or expose implementations in the standard project pattern instead of constructing them ad hoc throughout the codebase.

## Standard Project Structure

Code should follow the normal QMH loading pattern from a main application entry point.

Typical structure:

```text
src/
├── app.py or main.py              # application entry point
└── modules/
	├── __init__.py                # public module exports
	└── <module_name>/
		├── __init__.py
		├── module.py              # standard module, or factory entry point
		├── simulated.py           # optional factory implementation example
		├── tests/
		└── scripts/
```

The important structural rules are:

- The application entry point is responsible for creating the protocol and loading modules.
- Protocol, message, and base module support are provided by the `pyqmh` package.
- Modules should live under the shared modules package, not as scattered top-level scripts.
- The modules package should expose public module classes through its `__init__.py`.
- The main application should import modules from the modules package, instantiate them, and register or start them through the protocol-driven startup flow.
- Module addresses should be stable and predictable, commonly using snake_case names derived from the module class or responsibility.

## Main Application Loading Pattern

When authoring or modifying the app entry point, follow this mental model:

1. Create the protocol.
2. Import the modules that should participate in the application.
3. Instantiate each module with the dependencies it needs, especially the protocol.
4. Register, start, or attach each module using the project's established startup sequence.
5. Send actions through the protocol instead of invoking peer behavior directly.

Avoid designs where:

- module A directly owns module B's control flow
- modules import each other purely to call methods across boundaries
- the main application embeds business logic that should live inside a module

## Guidance for Copilot Changes

When assisting in this repository:

- Prefer changes that preserve message-driven boundaries.
- If a feature belongs to one runtime concern, place it in a module.
- If multiple backends are expected, prefer a factory module over condition-heavy monoliths.
- Keep the main entry point focused on wiring, startup, and orchestration.
- Keep protocol, message, and module abstractions central rather than duplicating queueing logic inside feature code.
- When creating a new module, prefer the `pyqmh-tools` package command `pyqmh_module_add` instead of manually scaffolding files when that tool is available and appropriate.
- When removing a module, prefer the `pyqmh-tools` package command `pyqmh_module_remove` instead of manually deleting files and references when that tool is available and appropriate.
