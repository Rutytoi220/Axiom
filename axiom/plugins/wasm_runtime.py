"""Wasm Runtime Engine for executing Sandboxed Plugins."""

import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import wasmtime

from axiom.plugins.loader import PluginManifest
from axiom.plugins.permissions import PermissionBroker
from axiom.plugins.exceptions import SandboxSecurityViolation

logger = logging.getLogger(__name__)


class WasmPluginRunner:
    """Executes a WebAssembly plugin within a strict WASI sandbox."""

    def __init__(self, manifest: PluginManifest, wasm_binary: bytes, workspace_dir: Path):
        self.manifest = manifest
        self.workspace_dir = workspace_dir
        
        config = wasmtime.Config()
        config.consume_fuel = True
        
        self.engine = wasmtime.Engine(config)
        self.module = wasmtime.Module(self.engine, wasm_binary)
        self.broker = PermissionBroker(manifest, workspace_dir)

    def execute(self, function_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an exported Wasm function and pass JSON via standard I/O."""
        # We construct a new store and linker per execution for absolute isolation.
        store = wasmtime.Store(self.engine)
        store.set_fuel(10_000_000)  # Resource constraints against infinite loops

        linker = wasmtime.Linker(self.engine)
        linker.define_wasi()

        # Memory export will be populated after instantiation
        memory_export = None

        # Define explicit host capability functions
        def axiom_log(ptr: int, length: int) -> None:
            if memory_export is None or not isinstance(memory_export, wasmtime.Memory):
                return
            data = memory_export.read(store, ptr, ptr + length)
            logger.info(f"[Wasm Plugin '{self.manifest.name}']: {data.decode('utf-8', errors='replace')}")

        def axiom_emit_event(ptr: int, length: int) -> None:
            if memory_export is None or not isinstance(memory_export, wasmtime.Memory):
                return
            data = memory_export.read(store, ptr, ptr + length)
            logger.info(f"[Wasm Plugin '{self.manifest.name}' Emits]: {data.decode('utf-8', errors='replace')}")

        def axiom_read_workspace(ptr: int, length: int) -> int:
            if memory_export is None or not isinstance(memory_export, wasmtime.Memory):
                return 0
                
            path_bytes = memory_export.read(store, ptr, ptr + length)
            requested_path = path_bytes.decode('utf-8', errors='replace')
            
            # Capability check
            # In a real setup, we use self.broker.check_read(requested_path)
            # For simplicity, if the manifest explicitly blocks fs read, we trap.
            if not getattr(self.manifest.permissions, "fs", {}).get("read", False):
                raise SandboxSecurityViolation(
                    plugin_id=getattr(self.manifest, "plugin_id", "unknown"),
                    violation_type="filesystem",
                    detail=f"Wasm Plugin attempted unauthorized workspace read: {requested_path}"
                )
            
            # If allowed, we could read and return a pointer, but for this exercise we just return a mock success code (1)
            return 1

        linker.define_func("env", "axiom_log", wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], []), axiom_log)
        linker.define_func("env", "axiom_emit_event", wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], []), axiom_emit_event)
        linker.define_func("env", "axiom_read_workspace", wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], [wasmtime.ValType.i32()]), axiom_read_workspace)


        wasi_config = self.broker.build_wasi_config()

        # To pass data via stdin/stdout without sharing memory, we use temporary files.
        # This completely isolates the Wasm guest from the host Python memory space.
        with tempfile.NamedTemporaryFile("w+", delete=False) as stdin_f, \
             tempfile.NamedTemporaryFile("w+", delete=False) as stdout_f:
             
            stdin_path = stdin_f.name
            stdout_path = stdout_f.name
            
            # Write the payload to stdin
            stdin_f.write(json.dumps(payload))
            stdin_f.flush()

        try:
            # Bind I/O
            wasi_config.stdin_file = stdin_path
            wasi_config.stdout_file = stdout_path
            
            # Set the WASI context on the store
            store.set_wasi(wasi_config)

            # Instantiate the module
            instance = linker.instantiate(store, self.module)
            
            # Retrieve memory export to be used by host closures
            memory_export = instance.exports(store).get("memory")
            
            # Get the exported function
            func = instance.exports(store).get(function_name)
            if not func:
                raise ValueError(f"Wasm module does not export function '{function_name}'")
                
            # Execute
            try:
                func(store)
            except wasmtime.Trap as trap:
                # Wasm traps (e.g. out of bounds memory, unauthorized WASI syscalls)
                logger.error(f"Plugin '{self.manifest.name}' trapped: {trap.message}")
                raise SandboxSecurityViolation(
                    plugin_id=getattr(self.manifest, "plugin_id", "unknown"),
                    violation_type="trap",
                    detail=f"Wasm sandbox trap: {trap.message}"
                ) from trap

            # Read result from stdout
            with open(stdout_path, "r") as out_f:
                result_str = out_f.read().strip()
                
            if not result_str:
                return {}
                
            try:
                return json.loads(result_str)
            except json.JSONDecodeError:
                # Plugin didn't return valid JSON
                return {"raw_output": result_str}
                
        finally:
            Path(stdin_path).unlink(missing_ok=True)
            Path(stdout_path).unlink(missing_ok=True)
