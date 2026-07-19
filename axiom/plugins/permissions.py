"""Capability-Based Permission Broker for Sandboxed Plugins.

Translates PluginManifest definitions into strict WASI boundaries.
"""

import logging
from pathlib import Path
from typing import Optional

import wasmtime

from axiom.plugins.loader import PluginManifest
from axiom.plugins.exceptions import PluginPermissionError

logger = logging.getLogger(__name__)


class PermissionBroker:
    """Enforces WASI sandbox boundaries based on the plugin manifest."""

    def __init__(self, manifest: PluginManifest, workspace_dir: Path):
        self.manifest = manifest
        self.workspace_dir = Path(workspace_dir).resolve()
        self.plugin_scratch_dir = self.workspace_dir / ".axiom" / "plugins" / manifest.plugin_id / "scratch"

    def build_wasi_config(self) -> wasmtime.WasiConfig:
        """Construct a secure WasiConfig according to granted permissions."""
        config = wasmtime.WasiConfig()
        config.inherit_stdin()
        config.inherit_stdout()
        config.inherit_stderr()

        # Filesystem isolation
        if self.manifest.permissions.allows("filesystem"):
            # Ensure scratch dir exists
            self.plugin_scratch_dir.mkdir(parents=True, exist_ok=True)
            # Map the host scratch dir to the guest's /scratch
            config.preopen_dir(str(self.plugin_scratch_dir), "/scratch")
            logger.debug(f"Plugin {self.manifest.name}: Granted filesystem access to /scratch")
        else:
            logger.debug(f"Plugin {self.manifest.name}: Filesystem access denied")

        # Network isolation
        # In WASI Preview 1, sockets are inherently unsupported by default in Wasmtime's Python SDK
        # unless specifically mapped. We strictly check the manifest flag.
        if self.manifest.permissions.allows("network"):
            # Acknowledge the requested network permission.
            logger.debug(f"Plugin {self.manifest.name}: Network access explicitly requested and approved by user.")
            # Wasmtime Python SDK doesn't natively expose `inherit_network()`.
            # True network capabilities would be injected via host imports.
            # We flag this in env vars so the plugin knows the host approved it.
            config.env = [("AXIOM_NETWORK_ENABLED", "1")]
        else:
            logger.debug(f"Plugin {self.manifest.name}: Network access denied")
            config.env = [("AXIOM_NETWORK_ENABLED", "0")]

        return config
