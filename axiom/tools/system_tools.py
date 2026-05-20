"""System tools for AXIOM."""

import subprocess
import os
from pathlib import Path
from typing import Optional, Any
import logging

from axiom.tools.base_tool import BaseTool, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


class ShellCommandTool(BaseTool):
    """Execute shell commands."""
    
    def __init__(self):
        super().__init__(
            tool_id="shell_command",
            name="Shell Command",
            description="Execute shell commands on the system"
        )
        self.add_parameter(ToolParameter(
            name="command",
            type="string",
            description="The shell command to execute",
            required=True
        ))
        self.add_parameter(ToolParameter(
            name="timeout",
            type="integer",
            description="Timeout in seconds",
            required=False,
            default=30
        ))
    
    def execute(self, command: str, timeout: int = 30, **kwargs) -> ToolResult:
        """Execute a shell command."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return ToolResult(
                success=result.returncode == 0,
                output={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode
                }
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output=None,
                error=f"Command timeout after {timeout} seconds"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )


class ReadFileTool(BaseTool):
    """Read file contents."""
    
    def __init__(self):
        super().__init__(
            tool_id="read_file",
            name="Read File",
            description="Read contents of a file"
        )
        self.add_parameter(ToolParameter(
            name="path",
            type="string",
            description="Path to the file to read",
            required=True
        ))
        self.add_parameter(ToolParameter(
            name="max_size",
            type="integer",
            description="Maximum size in bytes to read",
            required=False,
            default=1000000
        ))
    
    def execute(self, path: str, max_size: int = 1000000, **kwargs) -> ToolResult:
        """Read file contents."""
        try:
            file_path = Path(path)
            
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"File not found: {path}"
                )
            
            if file_path.stat().st_size > max_size:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"File too large: {file_path.stat().st_size} > {max_size}"
                )
            
            content = file_path.read_text()
            return ToolResult(
                success=True,
                output={
                    "path": path,
                    "content": content,
                    "size": len(content)
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )


class WriteFileTool(BaseTool):
    """Write content to a file."""
    
    def __init__(self):
        super().__init__(
            tool_id="write_file",
            name="Write File",
            description="Write content to a file"
        )
        self.add_parameter(ToolParameter(
            name="path",
            type="string",
            description="Path to the file to write",
            required=True
        ))
        self.add_parameter(ToolParameter(
            name="content",
            type="string",
            description="Content to write",
            required=True
        ))
        self.add_parameter(ToolParameter(
            name="append",
            type="boolean",
            description="Append to file if it exists",
            required=False,
            default=False
        ))
    
    def execute(self, path: str, content: str, append: bool = False, **kwargs) -> ToolResult:
        """Write to file."""
        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            if append and file_path.exists():
                file_path.write_text(file_path.read_text() + content)
            else:
                file_path.write_text(content)
            
            return ToolResult(
                success=True,
                output={
                    "path": path,
                    "size": len(content),
                    "mode": "append" if append else "write"
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )


class PythonExecTool(BaseTool):
    """Execute Python code safely."""
    
    def __init__(self):
        super().__init__(
            tool_id="python_exec",
            name="Python Exec",
            description="Execute Python code in a safe sandbox"
        )
        self.add_parameter(ToolParameter(
            name="code",
            type="string",
            description="Python code to execute",
            required=True
        ))
    
    def execute(self, code: str, **kwargs) -> ToolResult:
        """Execute Python code."""
        try:
            # Create safe execution environment
            safe_globals = {
                "__builtins__": {
                    "print": print,
                    "len": len,
                    "range": range,
                    "str": str,
                    "int": int,
                    "float": float,
                    "list": list,
                    "dict": dict,
                    "sum": sum,
                    "max": max,
                    "min": min,
                }
            }
            
            # Capture output
            output_buffer = []
            original_print = print
            
            def safe_print(*args, **kwargs):
                output_buffer.append(" ".join(str(a) for a in args))
            
            safe_globals["print"] = safe_print
            
            exec(code, safe_globals)
            
            return ToolResult(
                success=True,
                output={
                    "stdout": "\n".join(output_buffer),
                    "result": "Code executed successfully"
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )
