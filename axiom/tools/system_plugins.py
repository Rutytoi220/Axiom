import os
import tempfile
import uuid
from axiom.tools.base import axiom_tool, ToolResult
from axiom.security.sandbox import BwrapSandbox

_sandbox = BwrapSandbox()

@axiom_tool("execute_shell_command", "Executes a bash shell command within a restricted rootless sandbox.", {
    "command": {"type": "string", "description": "The shell command to run."},
    "allow_net": {"type": "boolean", "description": "Whether to allow network access. Defaults to false."}
})
def execute_shell_command(command: str, allow_net: bool = False):
    result = _sandbox.execute(command, allow_net=allow_net)
    success = result["exit_code"] == 0
    output_msg = f"Exit Code: {result['exit_code']}\nSTDOUT:\n{result['stdout']}\nSTDERR:\n{result['stderr']}"
    return ToolResult(success, output_msg)

@axiom_tool("run_python_script", "Executes Python code within a restricted rootless sandbox.", {
    "code": {"type": "string", "description": "The python code string to execute."},
    "allow_net": {"type": "boolean", "description": "Whether to allow network access. Defaults to false."}
})
def run_python_script(code: str, allow_net: bool = False):
    # Write the script into the safe workspace folder
    script_name = f"script_{uuid.uuid4().hex[:8]}.py"
    script_path = os.path.join(_sandbox.workspace_dir, script_name)
    
    try:
        with open(script_path, "w") as f:
            f.write(code)
            
        command = f"python3 {script_name}"
        result = _sandbox.execute(command, allow_net=allow_net)
        
        success = result["exit_code"] == 0
        output_msg = f"Exit Code: {result['exit_code']}\nSTDOUT:\n{result['stdout']}\nSTDERR:\n{result['stderr']}"
        return ToolResult(success, output_msg)
    finally:
        # Cleanup script
        if os.path.exists(script_path):
            os.remove(script_path)
