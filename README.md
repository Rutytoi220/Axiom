# AXIOM

AXIOM is a local-first AI execution system for coordinating tools, agents,
memory, and desktop automation without requiring a cloud control plane.

## Core capabilities

<div align="center">
  <img src="assets/demo.png" alt="AXIOM Terminal Output Demo" width="800">
  <p><em>AXIOM v1.0 executing a local tool sequence</em></p>
</div>

- Event-driven execution and component registries
- Local Ollama integration
- Persistent local memory
- Sandboxed file and shell tooling
- Deterministic execution plans with dependency tracking and confirmation gates

## Quick Start

### Installation

Clone the repository and install the package and its dependencies:

```bash
pip install -e .
```

### Usage

Start the interactive AXIOM terminal:

```bash
axiom
```

You can now chat with the orchestrator, ask for system `status`, view registered `tools`, or type `help` for more commands.

For a full guide on using tools, agents, and Python integration, see [QUICKSTART.md](QUICKSTART.md).

## Development

Run the tests with:

```bash
python -m pytest tests/
```

Build a distribution with:

```bash
python -m pip wheel --no-deps --no-build-isolation .
```
