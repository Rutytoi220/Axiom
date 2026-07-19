import pytest
import wasmtime
from pathlib import Path
from axiom.plugins.wasm_runtime import WasmPluginRunner
from axiom.plugins.loader import PluginManifest
from axiom.plugins.exceptions import SandboxSecurityViolation

class MockPermissions:
    def __init__(self, can_read=False):
        self.fs = {"read": can_read}
        self.network = False
        
    def allows(self, capability: str) -> bool:
        if capability == "filesystem":
            return self.fs.get("read", False)
        if capability == "network":
            return self.network
        return False

class MockManifest:
    def __init__(self, name="TestPlugin", can_read=False):
        self.name = name
        self.plugin_id = name.lower()
        self.permissions = MockPermissions(can_read)

# A WAT module that exports a "run" function which calls axiom_log
WAT_VALID = """
(module
    (import "env" "axiom_log" (func $axiom_log (param i32 i32)))
    (memory (export "memory") 1)
    (data (i32.const 0) "Hello from Wasm!")
    
    (func (export "run")
        ;; Call axiom_log with ptr=0, len=16
        i32.const 0
        i32.const 16
        call $axiom_log
    )
)
"""

# A WAT module that calls axiom_read_workspace
WAT_READ = """
(module
    (import "env" "axiom_read_workspace" (func $axiom_read_workspace (param i32 i32) (result i32)))
    (memory (export "memory") 1)
    (data (i32.const 0) "/tmp/secret.txt")
    
    (func (export "run")
        i32.const 0
        i32.const 15
        call $axiom_read_workspace
        drop
    )
)
"""

# A WAT module that loops infinitely
WAT_INFINITE = """
(module
    (memory (export "memory") 1)
    (func (export "run")
        loop $my_loop
            br $my_loop
        end
    )
)
"""

def test_wasm_valid_execution(tmp_path):
    wasm_binary = wasmtime.wat2wasm(WAT_VALID)
    manifest = MockManifest()
    runner = WasmPluginRunner(manifest, wasm_binary, tmp_path)
    
    # Should execute without errors
    result = runner.execute("run", {})
    assert result == {}

def test_wasm_security_violation_fs_read(tmp_path):
    wasm_binary = wasmtime.wat2wasm(WAT_READ)
    # Manifest blocks read access
    manifest = MockManifest(can_read=False)
    runner = WasmPluginRunner(manifest, wasm_binary, tmp_path)
    
    with pytest.raises(SandboxSecurityViolation) as exc:
        runner.execute("run", {})
        
    assert "attempted unauthorized workspace read" in str(exc.value)

def test_wasm_infinite_loop_fuel_trap(tmp_path):
    wasm_binary = wasmtime.wat2wasm(WAT_INFINITE)
    manifest = MockManifest()
    runner = WasmPluginRunner(manifest, wasm_binary, tmp_path)
    
    with pytest.raises(SandboxSecurityViolation) as exc:
        runner.execute("run", {})
        
    # Trap message will mention fuel
    assert "fuel" in str(exc.value) or "trap" in str(exc.value)
