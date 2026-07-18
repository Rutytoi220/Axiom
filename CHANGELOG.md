# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- GitHub issue templates and release workflows.
- `CHANGELOG.md`, `LICENSE`, and `CONTRIBUTING.md`.

## [1.0.0] - 2026-07-18
### Added
- Initial public release of AXIOM.
- Event-driven orchestrator loop with local Ollama integration.
- Unified asynchronous SQLite memory store (`aiosqlite`) with WAL mode.
- Interactive CLI built with `cmd.Cmd`.
- Secure `ShellTool` with user confirmation prompts.
- Built-in file read/write tools.
- Token-aware context management.

### Fixed
- Out of memory protection with default `llama3:8b` fallback.
- CLI interrupts gracefully handling ghost tasks in the async bridge.
- Packaging dependencies (`aiosqlite`, `psutil`, etc.).

### Changed
- Standardized packaging exclusively around `pyproject.toml`, removing legacy `setup.py`.
- Restructured codebase, moving starter templates to `examples/` and verifiers to `scripts/`.
