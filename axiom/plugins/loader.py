"""Plugin manifest parser and loader for AXIOM v2.

Validates ``plugin.toml`` files according to the schema specified in
RFC-001 and returns a strongly-typed ``PluginManifest`` dataclass.

AXIOM_VERSION_COMPAT is the installed AXIOM runtime version against which
all ``axiom_version`` semver specifiers are evaluated.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tomllib  # Python ≥ 3.11
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-reuse-of-import]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

from axiom.plugins.exceptions import (
    PluginManifestError,
    PluginPermissionError,
    PluginVersionError,
)

logger = logging.getLogger(__name__)

# The runtime AXIOM version used to evaluate plugin compatibility specifiers.
AXIOM_RUNTIME_VERSION = (2, 0, 0)

# All permission keys a plugin may declare.
VALID_PERMISSIONS = frozenset({"filesystem", "shell", "network", "desktop_ui"})


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class PluginPermissions:
    """Parsed permission block from ``plugin.toml``."""

    filesystem: bool = False
    shell: bool = False
    network: bool = False
    desktop_ui: bool = False

    def allows(self, permission: str) -> bool:
        return bool(getattr(self, permission, False))


@dataclass
class PluginManifest:
    """Strongly-typed representation of a validated ``plugin.toml``."""

    # [plugin] section
    name: str
    version: str
    description: str
    author: str
    license: str
    axiom_version: str          # semver specifier, e.g. ">=2.0.0"

    # [entrypoint] section
    module: str
    entry_class: str            # "class" key — avoids Python keyword

    # [permissions] section
    permissions: PluginPermissions

    # Source directory (where plugin.toml lives)
    plugin_dir: Path

    # Raw TOML for informational use
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def plugin_id(self) -> str:
        return self.name.lower().replace(" ", "-").replace("_", "-")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_semver(spec: str) -> tuple[str, tuple[int, ...]]:
    """Parse a simple semver specifier like ``>=2.0.0`` into (op, version_tuple)."""
    for op in (">=", "<=", "==", "!=", ">", "<"):
        if spec.startswith(op):
            parts = spec[len(op):].strip().split(".")
            return op, tuple(int(p) for p in parts)
    raise PluginManifestError(
        f"Unsupported semver specifier format: {spec!r}. "
        "Expected one of: >=, <=, ==, !=, >, <"
    )


def _check_version_compat(specifier: str) -> None:
    """Raise ``PluginVersionError`` if AXIOM_RUNTIME_VERSION does not satisfy specifier."""
    op, required = _parse_semver(specifier)
    runtime = AXIOM_RUNTIME_VERSION

    satisfied = {
        ">=": runtime >= required,
        "<=": runtime <= required,
        "==": runtime == required,
        "!=": runtime != required,
        ">":  runtime > required,
        "<":  runtime < required,
    }.get(op, False)

    if not satisfied:
        runtime_str = ".".join(str(v) for v in runtime)
        raise PluginVersionError(
            f"Plugin requires AXIOM {specifier}, but runtime is {runtime_str}."
        )


# ---------------------------------------------------------------------------
# Core loader
# ---------------------------------------------------------------------------


class PluginLoader:
    """Validates and loads a single ``plugin.toml`` manifest.

    Usage::

        loader = PluginLoader()
        manifest = loader.load_manifest(Path("/path/to/my_plugin"))
        plugin_instance = loader.instantiate(manifest)
    """

    def load_manifest(self, plugin_dir: Path) -> PluginManifest:
        """Parse and validate ``plugin_dir/plugin.toml``.

        Raises:
            PluginManifestError: Schema validation failure.
            PluginVersionError: AXIOM version incompatibility.
        """
        toml_path = plugin_dir / "plugin.toml"
        if not toml_path.is_file():
            raise PluginManifestError(
                f"No plugin.toml found in {plugin_dir}"
            )

        if tomllib is None:
            raise PluginManifestError(
                "No TOML parser available. Install Python ≥ 3.11 or `pip install tomli`."
            )

        with toml_path.open("rb") as fh:
            raw = tomllib.load(fh)

        return self._validate(raw, plugin_dir)

    def _validate(self, raw: Dict[str, Any], plugin_dir: Path) -> PluginManifest:
        """Validate the parsed TOML dict and return a ``PluginManifest``."""

        # -- [plugin] section -----------------------------------------------
        plugin_sec = raw.get("plugin")
        if not isinstance(plugin_sec, dict):
            raise PluginManifestError("Missing required [plugin] section in plugin.toml")

        required_plugin_keys = ("name", "version", "description", "author", "axiom_version")
        for key in required_plugin_keys:
            if key not in plugin_sec:
                raise PluginManifestError(
                    f"Missing required key '[plugin].{key}' in plugin.toml"
                )

        # version compatibility check
        _check_version_compat(plugin_sec["axiom_version"])

        # -- [entrypoint] section -------------------------------------------
        entry_sec = raw.get("entrypoint")
        if not isinstance(entry_sec, dict):
            raise PluginManifestError("Missing required [entrypoint] section in plugin.toml")
        if "module" not in entry_sec:
            raise PluginManifestError("Missing required key '[entrypoint].module'")
        if "class" not in entry_sec:
            raise PluginManifestError("Missing required key '[entrypoint].class'")

        # -- [permissions] section ------------------------------------------
        perm_sec = raw.get("permissions", {})
        if not isinstance(perm_sec, dict):
            raise PluginManifestError("[permissions] section must be a TOML table")

        unknown = set(perm_sec.keys()) - VALID_PERMISSIONS
        if unknown:
            raise PluginManifestError(
                f"Unknown permission keys: {unknown}. "
                f"Valid keys are: {sorted(VALID_PERMISSIONS)}"
            )

        permissions = PluginPermissions(
            filesystem=bool(perm_sec.get("filesystem", False)),
            shell=bool(perm_sec.get("shell", False)),
            network=bool(perm_sec.get("network", False)),
            desktop_ui=bool(perm_sec.get("desktop_ui", False)),
        )

        return PluginManifest(
            name=plugin_sec["name"],
            version=plugin_sec["version"],
            description=plugin_sec.get("description", ""),
            author=plugin_sec.get("author", ""),
            license=plugin_sec.get("license", ""),
            axiom_version=plugin_sec["axiom_version"],
            module=entry_sec["module"],
            entry_class=entry_sec["class"],
            permissions=permissions,
            plugin_dir=plugin_dir,
            raw=raw,
        )

    def instantiate(self, manifest: PluginManifest) -> Any:
        """Import the plugin module and instantiate the declared class.

        The plugin directory is temporarily added to ``sys.path`` so relative
        imports within the plugin package work correctly.  It is removed again
        after import to avoid polluting the import namespace.

        Raises:
            PluginManifestError: Module or class not found / import error.
        """
        plugin_dir_str = str(manifest.plugin_dir)
        added_to_path = False

        try:
            if plugin_dir_str not in sys.path:
                sys.path.insert(0, plugin_dir_str)
                added_to_path = True

            try:
                module = importlib.import_module(manifest.module)
            except ImportError as exc:
                raise PluginManifestError(
                    f"Cannot import plugin module '{manifest.module}': {exc}"
                ) from exc

            cls = getattr(module, manifest.entry_class, None)
            if cls is None:
                raise PluginManifestError(
                    f"Class '{manifest.entry_class}' not found in module '{manifest.module}'"
                )

            instance = cls()
            instance._plugin_id = manifest.plugin_id  # inject ID
            return instance

        finally:
            if added_to_path and plugin_dir_str in sys.path:
                sys.path.remove(plugin_dir_str)
