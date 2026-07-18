# AXIOM

[![CI/CD Pipeline](https://github.com/rutytoi/axiom/actions/workflows/release.yml/badge.svg)](https://github.com/rutytoi/axiom/actions/workflows/release.yml)
[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/release/python-3120/)

AXIOM is a local-first AI execution system for coordinating tools, agents, memory, and desktop automation without requiring a cloud control plane.

## Core capabilities

<div align="center">
  <!-- TODO: Record an animated GIF of AXIOM executing a multi-step local tool sequence and save it as assets/demo.gif -->
  <img src="assets/demo.gif" alt="AXIOM Terminal Output Demo" width="800">
  <p><em>AXIOM v1.0 executing a local tool sequence</em></p>
</div>

- Event-driven execution and component registries
- Local Ollama integration
- Persistent local memory
- Sandboxed file and shell tooling
- Deterministic execution plans with dependency tracking and confirmation gates

## Quick Start

### Installation

Clone the repository and install the package:

```bash
git clone https://github.com/rutytoi/axiom.git
cd axiom
pip install -e .
```

Note: You must have [Ollama](https://ollama.com/) installed and running locally.

### Usage

Start the interactive AXIOM terminal:

```bash
axiom
```

You can now chat with the orchestrator, ask for system `status`, view registered `tools`, or type `help` for more commands.

For a full guide on using tools, agents, and Python integration, see [QUICKSTART.md](QUICKSTART.md).

## Extending AXIOM

AXIOM is designed to be easily extensible. You can build your own agents and tools to customize the orchestration layer.
Check out the starter scripts in the `examples/` directory:
- [examples/example_custom_agent.py](examples/example_custom_agent.py) - How to build and register custom agents
- [examples/example_custom_tool.py](examples/example_custom_tool.py) - How to build custom tools

## Development

Run the tests with:

```bash
python -m pytest tests/
```

Build a distribution with:

```bash
python -m pip wheel --no-deps --no-build-isolation .
```
