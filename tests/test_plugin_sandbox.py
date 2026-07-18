"""Red-team unit tests for the AXIOM v2 Plugin Sandbox Engine.

These tests deliberately attempt to break out of the sandbox using common
escape techniques.  Every attempt must be blocked 100% of the time.

Test categories
---------------
A. Manifest validation (loader.py)
B. AST static analysis (sandbox.py)
C. Runtime multiprocessing isolation (sandbox.py)
D. Integration through PluginManager (manager.py)
E. Legitimate usage — ensure the sandbox does NOT over-block valid code
"""

from __future__ import annotations

import sys
import textwrap
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator

import pytest

from axiom.core.events import EventBus
from axiom.core.registry import Registry
from axiom.plugins.axiom_plugin import AxiomPlugin, HookResult
from axiom.plugins.exceptions import (
    PluginManifestError,
    PluginVersionError,
    SandboxSecurityViolation,
)
from axiom.plugins.loader import (
    PluginLoader,
    PluginManifest,
    PluginPermissions,
    AXIOM_RUNTIME_VERSION,
)
from axiom.plugins.manager import PluginManager
from axiom.plugins.sandbox import (
    SandboxedToolProxy,
    static_check_plugin_source,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_plugin(tmp_path: Path, toml: str, python: str, filename: str = "myplugin.py") -> Path:
    """Write plugin.toml and a Python module into *tmp_path*."""
    (tmp_path / "plugin.toml").write_text(toml, encoding="utf-8")
    (tmp_path / filename).write_text(python, encoding="utf-8")
    return tmp_path


def _minimal_toml(
    name: str = "test-plugin",
    axiom_version: str = ">=2.0.0",
    permissions: str = "",
    module: str = "myplugin",
    cls: str = "MyPlugin",
) -> str:
    return f"""
[plugin]
name = "{name}"
version = "1.0.0"
description = "Test plugin"
author = "tester"
axiom_version = "{axiom_version}"

[entrypoint]
module = "{module}"
class = "{cls}"

[permissions]
{permissions}
""".strip()


def _minimal_plugin_source(extra_code: str = "") -> str:
    return textwrap.dedent(f"""
        from axiom.plugins.axiom_plugin import AxiomPlugin, HookResult

        class MyPlugin(AxiomPlugin):
            def on_load(self, context):
                self.register_tool(
                    name="noop",
                    description="does nothing",
                    handler=self._noop,
                )
            def _noop(self, **kwargs):
                {extra_code or 'return {"ok": True}'}
    """).strip()


# ---------------------------------------------------------------------------
# A. Manifest Validation
# ---------------------------------------------------------------------------

class TestManifestValidation:
    """A suite of manifest parser tests."""

    def test_valid_manifest_loads(self, tmp_path):
        toml = _minimal_toml()
        _write_plugin(tmp_path, toml, _minimal_plugin_source())
        loader = PluginLoader()
        manifest = loader.load_manifest(tmp_path)
        assert manifest.name == "test-plugin"
        assert manifest.permissions.network is False
        assert manifest.permissions.filesystem is False

    def test_missing_plugin_section_raises(self, tmp_path):
        bad = "[entrypoint]\nmodule='x'\nclass='Y'"
        (tmp_path / "plugin.toml").write_text(bad)
        with pytest.raises(PluginManifestError, match="\\[plugin\\]"):
            PluginLoader().load_manifest(tmp_path)

    def test_missing_name_raises(self, tmp_path):
        toml = "[plugin]\nversion='1.0'\ndescription='x'\nauthor='y'\naxiom_version='>=2.0.0'\n[entrypoint]\nmodule='m'\nclass='C'"
        (tmp_path / "plugin.toml").write_text(toml)
        with pytest.raises(PluginManifestError, match="name"):
            PluginLoader().load_manifest(tmp_path)

    def test_missing_entrypoint_section_raises(self, tmp_path):
        toml = "[plugin]\nname='x'\nversion='1.0'\ndescription='x'\nauthor='y'\naxiom_version='>=2.0.0'"
        (tmp_path / "plugin.toml").write_text(toml)
        with pytest.raises(PluginManifestError, match="\\[entrypoint\\]"):
            PluginLoader().load_manifest(tmp_path)

    def test_missing_toml_raises(self, tmp_path):
        with pytest.raises(PluginManifestError, match="No plugin.toml"):
            PluginLoader().load_manifest(tmp_path)

    def test_unknown_permission_key_raises(self, tmp_path):
        toml = _minimal_toml(permissions="does_not_exist = true")
        (tmp_path / "plugin.toml").write_text(toml)
        with pytest.raises(PluginManifestError, match="Unknown permission"):
            PluginLoader().load_manifest(tmp_path)

    def test_permissions_default_all_false(self, tmp_path):
        toml = _minimal_toml(permissions="")
        _write_plugin(tmp_path, toml, _minimal_plugin_source())
        manifest = PluginLoader().load_manifest(tmp_path)
        assert not manifest.permissions.filesystem
        assert not manifest.permissions.shell
        assert not manifest.permissions.network
        assert not manifest.permissions.desktop_ui

    def test_explicit_network_permission_true(self, tmp_path):
        toml = _minimal_toml(permissions="network = true")
        _write_plugin(tmp_path, toml, _minimal_plugin_source())
        manifest = PluginLoader().load_manifest(tmp_path)
        assert manifest.permissions.network is True


class TestVersionCompat:
    def test_exact_version_match(self, tmp_path):
        ver = ".".join(str(v) for v in AXIOM_RUNTIME_VERSION)
        toml = _minimal_toml(axiom_version=f"=={ver}")
        _write_plugin(tmp_path, toml, _minimal_plugin_source())
        manifest = PluginLoader().load_manifest(tmp_path)
        assert manifest is not None

    def test_future_version_requirement_raises(self, tmp_path):
        toml = _minimal_toml(axiom_version=">=99.0.0")
        (tmp_path / "plugin.toml").write_text(toml)
        with pytest.raises(PluginVersionError, match="requires AXIOM"):
            PluginLoader().load_manifest(tmp_path)

    def test_ge_passes(self, tmp_path):
        toml = _minimal_toml(axiom_version=">=1.0.0")
        _write_plugin(tmp_path, toml, _minimal_plugin_source())
        manifest = PluginLoader().load_manifest(tmp_path)
        assert manifest is not None


# ---------------------------------------------------------------------------
# B. Static AST Analysis (pre-import scan)
# ---------------------------------------------------------------------------

class TestStaticASTScanner:
    """These tests prove the *static* scanner catches forbidden imports
    BEFORE any code runs."""

    def _scan(self, source: str, permissions: PluginPermissions, plugin_id: str = "test") -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "evil.py").write_text(source, encoding="utf-8")
            static_check_plugin_source(p, permissions, plugin_id)

    def _no_perms(self) -> PluginPermissions:
        return PluginPermissions()

    # Network
    def test_import_socket_blocked_without_network(self):
        with pytest.raises(SandboxSecurityViolation, match="network"):
            self._scan("import socket", self._no_perms())

    def test_import_requests_blocked(self):
        with pytest.raises(SandboxSecurityViolation, match="network"):
            self._scan("import requests", self._no_perms())

    def test_import_urllib_blocked(self):
        with pytest.raises(SandboxSecurityViolation, match="network"):
            self._scan("from urllib import request", self._no_perms())

    def test_import_httpx_blocked(self):
        with pytest.raises(SandboxSecurityViolation, match="network"):
            self._scan("import httpx", self._no_perms())

    def test_import_websockets_blocked(self):
        with pytest.raises(SandboxSecurityViolation, match="network"):
            self._scan("import websockets", self._no_perms())

    # Shell
    def test_import_subprocess_blocked_without_shell(self):
        with pytest.raises(SandboxSecurityViolation, match="shell"):
            self._scan("import subprocess", self._no_perms())

    def test_import_pty_blocked(self):
        with pytest.raises(SandboxSecurityViolation, match="shell"):
            self._scan("import pty", self._no_perms())

    # Allowed when permissions granted
    def test_import_socket_allowed_with_network_permission(self):
        perms = PluginPermissions(network=True)
        self._scan("import socket", perms)  # must NOT raise

    def test_import_subprocess_allowed_with_shell_permission(self):
        perms = PluginPermissions(shell=True)
        self._scan("import subprocess", perms)  # must NOT raise

    # Innocent imports pass
    def test_import_math_always_allowed(self):
        self._scan("import math", self._no_perms())  # must NOT raise

    def test_import_json_always_allowed(self):
        self._scan("import json", self._no_perms())  # must NOT raise


# ---------------------------------------------------------------------------
# C. Runtime Multiprocessing Isolation
# ---------------------------------------------------------------------------

class TestRuntimeSandbox:
    """These tests go past the AST scanner and verify that runtime attempts
    to escape the sandbox are also blocked."""

    def _make_proxy(
        self,
        tmp_path: Path,
        plugin_source: str,
        permissions: PluginPermissions,
        tool_name: str = "evil_tool",
    ) -> SandboxedToolProxy:
        toml = _minimal_toml(permissions=
            ("network = true" if permissions.network else "") + 
            ("\nshell = true" if permissions.shell else "") +
            ("\nfilesystem = true" if permissions.filesystem else "")
        )
        _write_plugin(tmp_path, toml, plugin_source)
        loader = PluginLoader()
        manifest = loader.load_manifest(tmp_path)
        manifest = PluginManifest(
            name=manifest.name,
            version=manifest.version,
            description=manifest.description,
            author=manifest.author,
            license=manifest.license,
            axiom_version=manifest.axiom_version,
            module=manifest.module,
            entry_class=manifest.entry_class,
            permissions=permissions,  # override with test permissions
            plugin_dir=tmp_path,
        )
        from axiom.plugins.axiom_plugin import PluginToolDefinition

        class FakeTool:
            name = tool_name
            description = "red team"
            handler = None
            parameters = []

        return SandboxedToolProxy(
            manifest=manifest,
            tool_def=PluginToolDefinition(
                name=tool_name,
                description="red team attempt",
                handler=None,
                parameters=[],
            ),
            timeout=10,
        )

    def test_runtime_network_blocked_no_permission(self, tmp_path):
        """Plugin tries to open a socket at runtime — must be blocked."""
        source = textwrap.dedent("""
            from axiom.plugins.axiom_plugin import AxiomPlugin
            class MyPlugin(AxiomPlugin):
                def on_load(self, ctx):
                    self.register_tool("evil_tool", "tries network", self._run)
                def _run(self, **kw):
                    import socket
                    s = socket.socket()
                    s.connect(("8.8.8.8", 53))
                    return {"result": "connected"}
        """)
        perms = PluginPermissions(network=False)
        proxy = self._make_proxy(tmp_path, source, perms)
        # The sandbox must raise SandboxSecurityViolation — never silently succeed
        with pytest.raises(SandboxSecurityViolation) as exc_info:
            proxy.execute()
        assert exc_info.value.violation_type == "runtime"

    def test_runtime_subprocess_blocked_no_permission(self, tmp_path):
        """Plugin tries to call subprocess.run — must be blocked."""
        source = textwrap.dedent("""
            from axiom.plugins.axiom_plugin import AxiomPlugin
            class MyPlugin(AxiomPlugin):
                def on_load(self, ctx):
                    self.register_tool("evil_tool", "tries shell", self._run)
                def _run(self, **kw):
                    import subprocess
                    out = subprocess.check_output(["id"])
                    return {"result": out.decode()}
        """)
        perms = PluginPermissions(shell=False)
        proxy = self._make_proxy(tmp_path, source, perms)
        with pytest.raises(SandboxSecurityViolation):
            proxy.execute()

    def test_runtime_file_outside_workspace_blocked(self, tmp_path):
        """Plugin tries to read /etc/passwd — must be blocked."""
        source = textwrap.dedent("""
            from axiom.plugins.axiom_plugin import AxiomPlugin
            class MyPlugin(AxiomPlugin):
                def on_load(self, ctx):
                    self.register_tool("evil_tool", "tries file", self._run)
                def _run(self, **kw):
                    with open("/etc/passwd") as fh:
                        return {"data": fh.read(100)}
        """)
        perms = PluginPermissions(filesystem=False)
        proxy = self._make_proxy(tmp_path, source, perms)
        with pytest.raises(SandboxSecurityViolation) as exc_info:
            proxy.execute()
        assert exc_info.value.violation_type == "runtime"

    def test_legitimate_tool_call_succeeds(self, tmp_path):
        """A well-behaved plugin with only pure computation works correctly."""
        source = textwrap.dedent("""
            import math
            from axiom.plugins.axiom_plugin import AxiomPlugin
            class MyPlugin(AxiomPlugin):
                def on_load(self, ctx):
                    self.register_tool("evil_tool", "pure math", self._run)
                def _run(self, x=2, **kw):
                    return {"result": math.sqrt(x)}
        """)
        perms = PluginPermissions()
        proxy = self._make_proxy(tmp_path, source, perms)
        result = proxy.execute(x=4)
        assert result.success is True
        assert result.output == {"result": 2.0}

    def test_sandbox_timeout_enforced(self, tmp_path):
        """An infinite-looping plugin is killed after timeout."""
        source = textwrap.dedent("""
            from axiom.plugins.axiom_plugin import AxiomPlugin
            class MyPlugin(AxiomPlugin):
                def on_load(self, ctx):
                    self.register_tool("evil_tool", "infinite loop", self._run)
                def _run(self, **kw):
                    while True:
                        pass
        """)
        perms = PluginPermissions()
        proxy = self._make_proxy(tmp_path, source, perms)
        proxy._timeout = 2  # 2-second timeout for fast tests

        result = proxy.execute()
        assert result.success is False
        assert "timed out" in (result.error or "").lower()


# ---------------------------------------------------------------------------
# D. PluginManager Integration
# ---------------------------------------------------------------------------

class TestPluginManager:
    def _make_manager(self, plugin_root: Path) -> PluginManager:
        registry = Registry()
        bus = EventBus()
        return PluginManager(
            registry=registry,
            event_bus=bus,
            plugin_root=plugin_root,
        )

    def test_load_all_finds_valid_plugin(self, tmp_path):
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        toml = _minimal_toml()
        _write_plugin(plugin_dir, toml, _minimal_plugin_source())

        manager = self._make_manager(tmp_path)
        results = manager.load_all()

        assert "my_plugin" in results
        assert results["my_plugin"] is True
        assert "test-plugin" in manager.loaded_plugins

    def test_security_violation_plugin_not_loaded(self, tmp_path):
        """A plugin with forbidden imports is quarantined, not registered."""
        plugin_dir = tmp_path / "evil"
        plugin_dir.mkdir()
        # Plugin imports socket without network permission
        source = "import socket\n" + _minimal_plugin_source()
        toml = _minimal_toml(permissions="")  # no network
        _write_plugin(plugin_dir, toml, source)

        manager = self._make_manager(tmp_path)
        results = manager.load_all()

        assert results.get("evil") is False
        assert "test-plugin" not in manager.loaded_plugins

    def test_invalid_manifest_plugin_not_loaded(self, tmp_path):
        """A plugin with a broken manifest is skipped gracefully."""
        plugin_dir = tmp_path / "broken"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.toml").write_text("[garbage]")
        (plugin_dir / "myplugin.py").write_text("")

        manager = self._make_manager(tmp_path)
        results = manager.load_all()

        assert results.get("broken") is False
        assert not manager.loaded_plugins

    def test_tools_registered_in_registry(self, tmp_path):
        plugin_dir = tmp_path / "good"
        plugin_dir.mkdir()
        toml = _minimal_toml()
        _write_plugin(plugin_dir, toml, _minimal_plugin_source())

        manager = self._make_manager(tmp_path)
        manager.load_all()

        tools = manager._registry.list_tools()
        assert any("test-plugin" in tid for tid in tools)

    def test_empty_plugin_dir_returns_empty(self, tmp_path):
        manager = self._make_manager(tmp_path)
        results = manager.load_all()
        assert results == {}

    def test_nonexistent_plugin_root_returns_empty(self, tmp_path):
        manager = self._make_manager(tmp_path / "does_not_exist")
        results = manager.load_all()
        assert results == {}

    def test_unload_removes_tools_from_registry(self, tmp_path):
        plugin_dir = tmp_path / "removable"
        plugin_dir.mkdir()
        toml = _minimal_toml()
        _write_plugin(plugin_dir, toml, _minimal_plugin_source())

        manager = self._make_manager(tmp_path)
        manager.load_all()

        assert manager.loaded_plugins
        plugin_id = manager.loaded_plugins[0]
        manager.unload(plugin_id)

        assert plugin_id not in manager.loaded_plugins
        tools = manager._registry.list_tools()
        assert not any(plugin_id in tid for tid in tools)


# ---------------------------------------------------------------------------
# E. AxiomPlugin base class
# ---------------------------------------------------------------------------

class TestAxiomPluginBase:
    def test_hook_result_continue(self):
        hr = HookResult.continue_execution()
        assert hr.proceed is True
        assert hr.reason is None

    def test_hook_result_abort(self):
        hr = HookResult.abort("blocked by policy")
        assert hr.proceed is False
        assert hr.reason == "blocked by policy"

    def test_hook_result_with_modified_args(self):
        hr = HookResult.continue_execution(modified_args={"x": 99})
        assert hr.proceed is True
        assert hr.modified_args == {"x": 99}

    def test_register_tool_adds_to_list(self):
        class DummyPlugin(AxiomPlugin):
            def on_load(self, ctx):
                self.register_tool("my_tool", "desc", lambda: None)

        p = DummyPlugin()
        p.on_load(object())
        assert len(p.tools) == 1
        assert p.tools[0].name == "my_tool"

    def test_default_before_hook_continues(self):
        class MinPlugin(AxiomPlugin):
            pass

        p = MinPlugin()
        result = p.before_tool_execute("x", {})
        assert result.proceed is True

    def test_default_on_event_is_noop(self):
        class MinPlugin(AxiomPlugin):
            pass

        p = MinPlugin()
        p.on_event("any_event")  # must not raise

    def test_default_on_shutdown_is_noop(self):
        class MinPlugin(AxiomPlugin):
            pass

        p = MinPlugin()
        p.on_shutdown()  # must not raise
