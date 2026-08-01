# ADR-004: Dynamic Plugin SDK with Manifest-Based Discovery and Sandboxed Execution

**Status:** Accepted  
**Date:** 2026-07-18  
**Authors:** AXIOM Core Team

---

## Context

AXIOM's tool system provides built-in capabilities (shell execution, file I/O, clipboard access, screen capture). However, the AI agent ecosystem moves faster than any single team can maintain. Community members, enterprise users, and hobbyists all want to extend AXIOM with custom tools — home automation controllers, proprietary API integrations, domain-specific code analyzers — without forking the core kernel.

We evaluated three approaches for extensibility:

1. **Direct source modification.** Contributors fork the repo, add their tool to `axiom/tools/`, and submit a PR. This gates every community contribution on our review cycle, pollutes the core repository with niche integrations, and creates merge conflicts. Unacceptable at scale.
2. **Python entrypoint-based plugin system (setuptools `entry_points`).** Standard in the Python ecosystem (used by pytest, tox, etc.), but requires each plugin to be a proper installable Python package with `setup.cfg` or `pyproject.toml`. Too high a barrier for a user who just wants to add one tool function.
3. **A dual-mode system: a lightweight `@axiom.tool` decorator for quick scripts, and a full `plugin.toml` manifest for production-grade plugins.** This serves both the casual hacker and the enterprise plugin vendor.

A critical secondary concern was **security**. AXIOM runs with the user's full OS permissions. A malicious or careless plugin could exfiltrate data, delete files, or open network backdoors. We needed a mandatory security layer.

## Decision

We implemented a two-tier plugin architecture:

### Tier 1: The `@axiom.tool` Decorator SDK ([sdk/plugin.py](file:///home/rutytoi/Documents/ChienGPT/axiom/sdk/plugin.py))

For the simplest use case — a single Python file dropped into `~/.config/axiom/plugins/` — we provide a decorator-based registration:

```python
# ~/.config/axiom/plugins/my_weather.py
from axiom.sdk.plugin import tool

@tool(name="get_weather", description="Fetch weather for a city")
def get_weather(city: str) -> str:
    import requests
    r = requests.get(f"https://wttr.in/{city}?format=3")
    return r.text
```

The `@tool` decorator captures the function, its name, description, and module, registering it in a global `_PLUGIN_REGISTRY` dict. The `PluginLoaderService` ([engine/plugin_loader.py](file:///home/rutytoi/Documents/ChienGPT/axiom/engine/plugin_loader.py)) scans `~/.config/axiom/plugins/` on daemon boot, dynamically imports each `.py` file via `importlib.util.spec_from_file_location()`, and collects all registered tools.

### Tier 2: Manifest-Based Plugin Packages ([plugins/loader.py](file:///home/rutytoi/Documents/ChienGPT/axiom/plugins/loader.py) + [plugins/manager.py](file:///home/rutytoi/Documents/ChienGPT/axiom/plugins/manager.py))

For production-grade plugins that need explicit permissions, version gating, and sandboxed execution, we require a `plugin.toml` manifest inside a subdirectory of `~/.axiom/plugins/`:

```toml
[plugin]
name = "Home Assistant Bridge"
version = "1.2.0"
description = "Integrates AXIOM with Home Assistant for smart home control"
author = "Community Contributor"
axiom_version = ">=2.0.0"

[entrypoint]
module = "ha_bridge"
class = "HomeAssistantPlugin"

[permissions]
network = true
filesystem = false
shell = false
desktop_ui = false
```

The `PluginManager` orchestrates a strict 8-step loading pipeline:

1. **Discovery** — Scans `~/.axiom/plugins/` for subdirectories containing `plugin.toml`.
2. **Manifest Validation** — The `PluginLoader` parses the TOML file into a strongly-typed `PluginManifest` dataclass, enforcing required fields (`name`, `version`, `axiom_version`, `entrypoint`).
3. **Version Compatibility Check** — The `axiom_version` specifier (e.g., `>=2.0.0`) is validated against the running AXIOM runtime via semver comparison. Incompatible plugins are rejected immediately.
4. **Static Security Scan** — `static_check_plugin_source()` performs an AST-level scan of the plugin's source code, checking for disallowed operations that violate the declared permissions (e.g., a plugin without `shell = true` calling `subprocess.run()`).
5. **Instantiation** — The plugin's entry class is imported and instantiated. The plugin directory is temporarily prepended to `sys.path` during import and removed immediately after.
6. **Lifecycle Hook** — `plugin.on_load(context)` is called with a `_PluginLoadContext` that provides controlled access to environment variables (secrets).
7. **Tool Sandboxing** — Each tool exposed by the plugin is wrapped in a `SandboxedToolProxy` that enforces execution timeouts and permission boundaries.
8. **Registration & EventBus Binding** — Sandboxed tools are registered in the core `Registry`, and `plugin.on_event` is subscribed to the global `EventBus` wildcard (`*`), allowing plugins to react to any system event.

### Permission Model

The `PluginPermissions` dataclass defines four granular capabilities:

| Permission | Grants |
|-----------|--------|
| `filesystem` | Read/write access to the local filesystem |
| `shell` | Ability to execute shell commands |
| `network` | Outbound HTTP/socket connections |
| `desktop_ui` | PySide6 GUI widget injection |

Undeclared permissions default to `false`. Unknown permission keys in the manifest cause an immediate load failure with a clear error message listing the valid set.

### Hot-Unloading

The `PluginManager.unload(plugin_id)` method executes a clean teardown: calling the plugin's `on_shutdown()` lifecycle hook, de-registering all tools prefixed with `{plugin_id}::`, unregistering the plugin from the core registry, and removing it from the loaded state. This enables runtime plugin management without restarting the daemon.

## Consequences

### Positive

- **Zero-barrier community contributions.** A single `.py` file with `@axiom.tool` is all it takes to extend AXIOM. No packaging, no PRs, no forking. Drop the file in `~/.config/axiom/plugins/` and restart.
- **Core kernel remains clean.** Third-party integrations never touch `axiom/tools/` or `axiom/plugins/`. The core repository stays focused on infrastructure.
- **Defense in depth via static analysis + sandboxing.** The AST scanner catches obvious security violations at load time. The `SandboxedToolProxy` enforces runtime timeouts. The permission model ensures plugins can only access what they declare.
- **EventBus integration is automatic.** Plugins subscribed to `*` can observe and react to any system event (agent completions, tool calls, telemetry) without any additional wiring.
- **Version gating prevents silent breakage.** A plugin built for AXIOM 1.x will fail loudly on AXIOM 2.x rather than silently malfunctioning.

### Negative

- **Tier 1 (`@axiom.tool`) lacks security enforcement.** Scripts in `~/.config/axiom/plugins/` are imported directly via `importlib` with no sandboxing. They execute with the full permissions of the AXIOM process. This is a conscious tradeoff for simplicity — the user explicitly opted in by placing the file there.
- **Static AST analysis is not foolproof.** A determined attacker can bypass the static scanner using `eval()`, dynamic `__import__()`, or obfuscated bytecode. The scan is a best-effort deterrent, not a security boundary. True isolation would require `bwrap` or WASM sandboxing (implemented separately in the `SandboxRuntime`).
- **Plugin discovery is filesystem-based, not registry-based.** There is no centralized AXIOM plugin marketplace or `pip`-like package index. Users must manually download plugin directories. This is intentional (local-first philosophy), but limits discoverability.
- **`sys.path` mutation during import.** Temporarily prepending the plugin directory to `sys.path` can cause import namespace collisions if a plugin includes a module with the same name as a stdlib or AXIOM internal module. The path is removed immediately after import, but the risk exists during the import window.
