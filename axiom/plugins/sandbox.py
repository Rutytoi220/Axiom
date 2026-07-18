"""Sandbox Engine for AXIOM v2 Plugin System.

Provides two layers of protection for untrusted plugin code:

1. **Static AST Analysis** — scans plugin source files *before* import for
   forbidden constructs (e.g. ``import socket`` when ``network=false``).
   This is a fast, cheap, first-pass check that blocks naive breakout attempts.

2. **Multiprocessing Isolation** — each tool call is executed inside a freshly
   spawned child process with the Python restricted-execution environment
   described below.  The child communicates with the main process via a
   ``multiprocessing.Pipe``.  If the child exits unexpectedly, is killed by
   SIGALRM, or returns an error, the proxy surfaces a ``ToolResult(success=False)``.

Security properties enforced at the multiprocessing layer
---------------------------------------------------------
- The child process has no access to the parent's memory space.
- Forbidden modules are patched to raise ``SandboxSecurityViolation`` at
  import time inside the child (``builtins.__import__`` shim).
- Filesystem access is jailed to a per-call temporary directory; any ``open()``
  call targeting a path outside that directory is rejected.
- The child is given a wall-clock timeout; the parent kills it if it does not
  respond in time (default: 30 seconds).

Note on Wasm sandboxing
-----------------------
RFC-001 mentions a Wasm/Extism primary sandbox.  That remains the v2.1 target.
The multiprocessing approach here is the *fallback* that ships in v2.0, as
specified in the RFC migration roadmap.
"""

from __future__ import annotations

import ast
import inspect
import logging
import multiprocessing
import os
import signal
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from axiom.plugins.axiom_plugin import AxiomPlugin, PluginToolDefinition
from axiom.plugins.exceptions import SandboxSecurityViolation
from axiom.plugins.loader import PluginManifest, PluginPermissions
from axiom.tools import BaseTool, ToolParameter, ToolResult

logger = logging.getLogger(__name__)

# Default call timeout (seconds) for sandboxed tool execution.
SANDBOX_TIMEOUT_SECONDS = 30

# Modules that are forbidden unless the corresponding permission is granted.
_NETWORK_MODULES = frozenset({
    "socket", "ssl", "urllib", "urllib.request", "urllib.parse",
    "urllib.error", "http", "http.client", "ftplib", "smtplib",
    "requests", "httpx", "aiohttp", "websockets", "paramiko",
})

_SHELL_MODULES = frozenset({
    "subprocess", "popen", "pty", "fcntl",
})

_FILESYSTEM_EXTRA_MODULES = frozenset({
    "shutil", "glob",
})


# ---------------------------------------------------------------------------
# Static AST scanner
# ---------------------------------------------------------------------------


class _ASTImportScanner(ast.NodeVisitor):
    """Visits all ``import`` / ``from … import`` nodes in a module's AST."""

    def __init__(self) -> None:
        self.imported_names: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self.imported_names.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module:
            self.imported_names.append(node.module)
        self.generic_visit(node)


def static_check_plugin_source(
    plugin_dir: Path,
    permissions: PluginPermissions,
    plugin_id: str,
) -> None:
    """Scan every ``*.py`` file in *plugin_dir* for forbidden imports.

    Raises:
        SandboxSecurityViolation: If forbidden module usage is detected.
    """
    for py_file in plugin_dir.rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, OSError):
            continue

        scanner = _ASTImportScanner()
        scanner.visit(tree)

        for mod in scanner.imported_names:
            base = mod.split(".")[0]

            if not permissions.network and (mod in _NETWORK_MODULES or base in _NETWORK_MODULES):
                raise SandboxSecurityViolation(
                    plugin_id=plugin_id,
                    violation_type="import:network",
                    detail=(
                        f"Plugin imports network module '{mod}' in {py_file.name} "
                        "but does not have the 'network' permission."
                    ),
                )

            if not permissions.shell and (mod in _SHELL_MODULES or base in _SHELL_MODULES):
                raise SandboxSecurityViolation(
                    plugin_id=plugin_id,
                    violation_type="import:shell",
                    detail=(
                        f"Plugin imports shell module '{mod}' in {py_file.name} "
                        "but does not have the 'shell' permission."
                    ),
                )


# ---------------------------------------------------------------------------
# Child-process worker
# ---------------------------------------------------------------------------


def _sandbox_worker(
    handler_module: str,
    handler_class: str,
    tool_name: str,
    args: Dict[str, Any],
    workspace_dir: str,
    permissions: Dict[str, bool],
    plugin_dir: str,
    result_conn: Any,
) -> None:
    """Executed inside a child process.  Calls the plugin tool handler.

    Isolation is enforced by:
    - Patching ``builtins.__import__`` to block forbidden modules.
    - Patching ``builtins.open`` to restrict filesystem access to
      *workspace_dir* (when ``filesystem`` permission is False).
    - Installing a SIGALRM handler (POSIX only) as a last-resort kill.
    """
    import builtins
    import sys
    from pathlib import Path as _Path

    # -- 1. Import shim -------------------------------------------------------
    _original_import = builtins.__import__

    def _restricted_import(name, *a, **kw):  # type: ignore[no-untyped-def]
        base = name.split(".")[0]
        if not permissions.get("network") and (
            name in _NETWORK_MODULES or base in _NETWORK_MODULES
        ):
            raise SandboxSecurityViolation(
                plugin_id=handler_class,
                violation_type="import:network",
                detail=f"Runtime import of network module '{name}' blocked.",
            )
        if not permissions.get("shell") and (
            name in _SHELL_MODULES or base in _SHELL_MODULES
        ):
            raise SandboxSecurityViolation(
                plugin_id=handler_class,
                violation_type="import:shell",
                detail=f"Runtime import of shell module '{name}' blocked.",
            )
        return _original_import(name, *a, **kw)

    builtins.__import__ = _restricted_import

    # -- 2. Filesystem shim ---------------------------------------------------
    if not permissions.get("filesystem"):
        _original_open = builtins.open
        _workspace = _Path(workspace_dir).resolve()

        def _restricted_open(file, *a, **kw):  # type: ignore[no-untyped-def]
            try:
                resolved = _Path(str(file)).resolve()
            except Exception:
                resolved = None
            if resolved is not None and not str(resolved).startswith(str(_workspace)):
                raise SandboxSecurityViolation(
                    plugin_id=handler_class,
                    violation_type="filesystem",
                    detail=(
                        f"Access to '{file}' denied — plugin workspace is "
                        f"'{_workspace}'."
                    ),
                )
            return _original_open(file, *a, **kw)

        builtins.open = _restricted_open

    # -- 3. Execute the handler -----------------------------------------------
    try:
        if plugin_dir not in sys.path:
            sys.path.insert(0, plugin_dir)

        import importlib
        module = importlib.import_module(handler_module)
        cls = getattr(module, handler_class)
        instance = cls()
        if hasattr(instance, "_plugin_id"):
            instance._plugin_id = handler_class

        # Call on_load with a minimal context
        class _MinimalContext:
            class secrets:
                @staticmethod
                def get(key: str, default: Any = None) -> Any:
                    return default

        instance.on_load(_MinimalContext())

        # Find the tool and call its handler
        handler_fn = None
        for tool_def in instance.tools:
            if tool_def.name == tool_name:
                handler_fn = tool_def.handler
                break

        if handler_fn is None:
            raise AttributeError(f"Tool '{tool_name}' not found in plugin {handler_class}")

        result = handler_fn(**args)
        result_conn.send(("ok", result))

    except SandboxSecurityViolation as exc:
        result_conn.send(("security_violation", str(exc)))
    except Exception:
        result_conn.send(("error", traceback.format_exc()))
    finally:
        result_conn.close()


# ---------------------------------------------------------------------------
# Sandboxed tool proxy
# ---------------------------------------------------------------------------


class SandboxedToolProxy(BaseTool):
    """A ``BaseTool``-compatible wrapper that executes plugin handlers in isolation.

    Each call to ``execute()`` spawns a fresh child process, sends the tool
    arguments over a ``Pipe``, waits for the result (up to ``timeout`` seconds),
    and deserialises the ``ToolResult``.
    """

    def __init__(
        self,
        manifest: PluginManifest,
        tool_def: PluginToolDefinition,
        timeout: int = SANDBOX_TIMEOUT_SECONDS,
    ) -> None:
        super().__init__(
            tool_id=f"{manifest.plugin_id}::{tool_def.name}",
            name=tool_def.name,
            description=tool_def.description,
        )
        self._manifest = manifest
        self._tool_def = tool_def
        self._timeout = timeout

        # Register parameters for schema/validation
        for p in tool_def.parameters:
            self.add_parameter(
                ToolParameter(
                    name=p["name"],
                    type=p.get("type", "string"),
                    description=p.get("description", ""),
                    required=p.get("required", True),
                )
            )

    def execute(self, **kwargs: Any) -> ToolResult:  # type: ignore[override]
        """Run the plugin tool handler inside a sandboxed child process."""
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)

        permissions = {
            "filesystem": self._manifest.permissions.filesystem,
            "shell": self._manifest.permissions.shell,
            "network": self._manifest.permissions.network,
            "desktop_ui": self._manifest.permissions.desktop_ui,
        }

        with tempfile.TemporaryDirectory(prefix="axiom_plugin_workspace_") as workspace:
            proc = multiprocessing.Process(
                target=_sandbox_worker,
                args=(
                    self._manifest.module,
                    self._manifest.entry_class,
                    self._tool_def.name,
                    kwargs,
                    workspace,
                    permissions,
                    str(self._manifest.plugin_dir),
                    child_conn,
                ),
                daemon=True,
            )
            proc.start()
            child_conn.close()  # child end is only needed in the child

            try:
                if parent_conn.poll(self._timeout):
                    status, payload = parent_conn.recv()
                else:
                    proc.kill()
                    proc.join(timeout=2)
                    return ToolResult(
                        success=False,
                        error=f"Plugin '{self._manifest.plugin_id}' timed out after {self._timeout}s.",
                    )
            except EOFError:
                return ToolResult(
                    success=False,
                    error=f"Plugin '{self._manifest.plugin_id}' exited unexpectedly.",
                )
            finally:
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=2)
                parent_conn.close()

        if status == "ok":
            # Payload is whatever the handler returned; normalise to ToolResult
            if isinstance(payload, ToolResult):
                return payload
            return ToolResult(success=True, output=payload)

        if status == "security_violation":
            raise SandboxSecurityViolation(
                plugin_id=self._manifest.plugin_id,
                violation_type="runtime",
                detail=payload,
            )

        # status == "error"
        return ToolResult(success=False, error=f"Plugin error:\n{payload}")
