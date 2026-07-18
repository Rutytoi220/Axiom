"""PluginManager — discovery, loading, and EventBus integration.

Scans ``~/.axiom/plugins/`` (configurable) for subdirectories containing a
``plugin.toml``.  For each found manifest:

1. Validates the manifest via ``PluginLoader``.
2. Runs the static AST security scan via ``static_check_plugin_source``.
3. Instantiates the plugin class.
4. Calls ``plugin.on_load(context)``.
5. Wraps each tool in a ``SandboxedToolProxy``.
6. Registers the proxied tools in the ``core.Registry``.
7. Subscribes ``plugin.on_event`` to the global EventBus.
8. Emits ``plugin.loaded`` or ``plugin.error`` events.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from axiom.plugins.axiom_plugin import AxiomPlugin
from axiom.plugins.exceptions import PluginError, SandboxSecurityViolation
from axiom.plugins.loader import PluginLoader, PluginManifest
from axiom.plugins.sandbox import SandboxedToolProxy, static_check_plugin_source

logger = logging.getLogger(__name__)

# Default discovery directory
DEFAULT_PLUGIN_DIR = Path.home() / ".axiom" / "plugins"


class _PluginLoadContext:
    """Minimal context object passed to ``plugin.on_load``."""

    class secrets:  # noqa: N801
        @staticmethod
        def get(key: str, default: Any = None) -> Any:
            import os
            return os.environ.get(key, default)


class PluginManager:
    """Discovers, validates, sandboxes, and registers all plugins.

    Typical usage (called from ``Engine.initialize`` or the CLI)::

        manager = PluginManager(registry=engine.registry, event_bus=engine.event_bus)
        manager.load_all()
    """

    def __init__(
        self,
        registry: Any,
        event_bus: Any,
        plugin_root: Path = DEFAULT_PLUGIN_DIR,
        sandbox_timeout: int = 30,
    ) -> None:
        self._registry = registry
        self._event_bus = event_bus
        self._plugin_root = plugin_root
        self._sandbox_timeout = sandbox_timeout
        self._loader = PluginLoader()
        self._loaded: Dict[str, AxiomPlugin] = {}

    # -- Public API ----------------------------------------------------------

    def load_all(self) -> Dict[str, bool]:
        """Discover and load all plugins found in ``plugin_root``.

        Returns a dict of ``{plugin_id: success}`` for reporting.
        """
        results: Dict[str, bool] = {}
        if not self._plugin_root.is_dir():
            logger.debug("Plugin root %s does not exist — no plugins loaded.", self._plugin_root)
            return results

        for candidate in sorted(self._plugin_root.iterdir()):
            if not candidate.is_dir():
                continue
            toml_path = candidate / "plugin.toml"
            if not toml_path.is_file():
                continue

            try:
                success = self._load_one(candidate)
                results[candidate.name] = success
            except Exception as exc:
                logger.error("Failed to load plugin at %s: %s", candidate, exc)
                results[candidate.name] = False

        return results

    def load_from_path(self, plugin_dir: Path) -> bool:
        """Load a single plugin from the given directory path."""
        return self._load_one(plugin_dir)

    def unload(self, plugin_id: str) -> None:
        """Call ``on_shutdown`` and de-register all tools from a loaded plugin."""
        plugin = self._loaded.get(plugin_id)
        if plugin is None:
            logger.warning("Cannot unload unknown plugin '%s'", plugin_id)
            return

        try:
            plugin.on_shutdown()
        except Exception as exc:
            logger.error("Error during shutdown of plugin '%s': %s", plugin_id, exc)

        # Unregister all tools contributed by this plugin
        for tool_id in list(self._registry.list_tools().keys()):
            if tool_id.startswith(f"{plugin_id}::"):
                self._registry.unregister_tool(tool_id)

        self._registry.unregister_plugin(plugin_id)
        del self._loaded[plugin_id]
        logger.info("Plugin '%s' unloaded.", plugin_id)

    @property
    def loaded_plugins(self) -> List[str]:
        return list(self._loaded.keys())

    # -- Private helpers -----------------------------------------------------

    def _load_one(self, plugin_dir: Path) -> bool:
        """Load, validate, and register a single plugin.  Returns True on success."""
        plugin_id = "(unknown)"
        try:
            # 1. Parse manifest
            manifest: PluginManifest = self._loader.load_manifest(plugin_dir)
            plugin_id = manifest.plugin_id
            logger.info("Loading plugin '%s' v%s …", manifest.name, manifest.version)

            # 2. Static AST security scan
            static_check_plugin_source(plugin_dir, manifest.permissions, plugin_id)

            # 3. Instantiate
            instance: AxiomPlugin = self._loader.instantiate(manifest)

            # 4. on_load
            instance.on_load(_PluginLoadContext())

            # 5. Subscribe on_event to the EventBus
            self._event_bus.subscribe("*", instance.on_event)

            # 6. Wrap each tool in a SandboxedToolProxy and register
            for tool_def in instance.tools:
                proxy = SandboxedToolProxy(
                    manifest=manifest,
                    tool_def=tool_def,
                    timeout=self._sandbox_timeout,
                )
                self._registry.register_tool(proxy.tool_id, proxy)
                logger.debug(
                    "  Registered sandboxed tool '%s' from plugin '%s'",
                    proxy.tool_id,
                    plugin_id,
                )

            # 7. Register the plugin instance itself
            self._registry.register_plugin(plugin_id, instance)
            self._loaded[plugin_id] = instance

            # 8. Emit success event
            self._emit("plugin.loaded", {
                "plugin_id": plugin_id,
                "version": manifest.version,
                "tool_count": len(instance.tools),
            })
            logger.info("Plugin '%s' loaded successfully (%d tools).", plugin_id, len(instance.tools))
            return True

        except SandboxSecurityViolation as exc:
            logger.error("Security violation loading plugin '%s': %s", plugin_id, exc)
            self._emit("plugin.error", {"plugin_id": plugin_id, "reason": str(exc), "type": "security"})
            return False
        except PluginError as exc:
            logger.error("Plugin error loading '%s': %s", plugin_id, exc)
            self._emit("plugin.error", {"plugin_id": plugin_id, "reason": str(exc), "type": "manifest"})
            return False
        except Exception as exc:
            logger.error("Unexpected error loading plugin at %s: %s", plugin_dir, exc, exc_info=True)
            self._emit("plugin.error", {"plugin_id": plugin_id, "reason": str(exc), "type": "unknown"})
            return False

    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        try:
            from axiom.core.events import Event
            self._event_bus.publish(
                Event(event_type=event_type, source="PluginManager", data=data)
            )
        except Exception:
            pass  # Never let EventBus failure break the plugin loader
