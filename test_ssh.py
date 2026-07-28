from axiom.tools.ssh_teleport import SSHTeleportTool
from axiom.engine.security import SecuritySandbox

tool = SSHTeleportTool()
res = tool(target="localhost", command="echo 'Hello SSH'", timeout=2)
print("Tool result:", res)

# Test Sandbox
sandbox = SecuritySandbox()
allowed, msg = sandbox.evaluate_command("TestAgent", "ssh_teleport", {"target": "localhost", "command": "uname -a"})
print(f"Sandbox Allowed: {allowed}, Msg: {msg}")
