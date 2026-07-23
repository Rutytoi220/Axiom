# Changelog

## [1.0.0] - 2026-07-23

### Added
- **MCP Server Federation**: Added Server-Sent Events (SSE) transport layer for remote MCP server connections.
- **Desktop Automation Macro Recorder**: Added visual dashboard for macro recording and live replay states over WebSocket EventBus.
- **Autonomous SWE-Bench Benchmark Engine**: Integrated `swe_harness.py` with multi-agent consensus loop.
- **Visual GUI Automation Loop**: Bridged Set-of-Mark vision pipeline with desktop automation engine.
- **Type Hardening**: Comprehensive strict type annotations across the `axiom/` core library.
- **System Hardening**: Graceful degradation under heavy load, robust Qdrant initialization lock management, and concurrent task isolation.

### Changed
- Refactored `axiom/perception/vision_pipeline.py` to use `mss` as a fallback on Linux if `pygetwindow` fails.
- Fixed IO deadlocks by isolating daemon imports from the `CLI` entrypoint.

### Removed
- Unused eager imports in `axiom/__init__.py`.
