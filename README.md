# AXIOM

AXIOM is a local-first AI execution system for coordinating tools, agents,
memory, and desktop automation without requiring a cloud control plane.

## Core capabilities

- Event-driven execution and component registries
- Local Ollama integration
- Persistent local memory
- Sandboxed file and shell tooling
- Deterministic execution plans with dependency tracking and confirmation gates

## Development

Run the tests with:

```bash
python -m pytest
```

Build a distribution with:

```bash
python -m pip wheel --no-deps --no-build-isolation .
```
