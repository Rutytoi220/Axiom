"""AXIOM Plugins Module — Extensible plugin system (v1 + v2 API)."""

# v1 legacy plugins (kept for backward compatibility)
from axiom.plugins.base_plugin import BasePlugin
from axiom.plugins.nxbt_plugin import NXBTPlugin
from axiom.plugins.automation_plugin import AutomationPlugin

# v2 Plugin Ecosystem (RFC-001)
from axiom.plugins.axiom_plugin import AxiomPlugin, HookResult, PluginToolDefinition
from axiom.plugins.exceptions import (
    PluginError,
    PluginManifestError,
    PluginPermissionError,
    PluginVersionError,
    SandboxSecurityViolation,
)
from axiom.plugins.loader import PluginLoader, PluginManifest, PluginPermissions
from axiom.plugins.sandbox import SandboxedToolProxy, static_check_plugin_source
from axiom.plugins.manager import PluginManager

__all__ = [
    # v1
    "BasePlugin",
    "NXBTPlugin",
    "AutomationPlugin",
    # v2 core
    "AxiomPlugin",
    "HookResult",
    "PluginToolDefinition",
    # exceptions
    "PluginError",
    "PluginManifestError",
    "PluginPermissionError",
    "PluginVersionError",
    "SandboxSecurityViolation",
    # loader
    "PluginLoader",
    "PluginManifest",
    "PluginPermissions",
    # sandbox
    "SandboxedToolProxy",
    "static_check_plugin_source",
    # manager
    "PluginManager",
]
