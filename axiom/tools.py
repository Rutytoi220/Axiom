"""Tool system for AXIOM."""

import asyncio
import logging
import subprocess
import os
import shlex
import platform
import shutil
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ToolResult:
    """Represents the result of a tool execution."""
    
    def __init__(self, success: bool, output: Any = None, error: Optional[str] = None, metadata: Optional[Dict] = None):
        self.success = success
        self.output = output
        self.error = error
        self.metadata = metadata or {}

    def __repr__(self):
        if self.success:
            return f"ToolResult(success={self.success}, output={self.output!r})"
        return f"ToolResult(success={self.success}, error={self.error!r})"

    def to_dict(self, tool: str = "", arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return the strict AXIOM tool-result envelope."""
        result = {"output": self.output, "error": self.error, "metadata": self.metadata}
        return {
            "tool": tool,
            "arguments": arguments or {},
            "result": result,
            "success": bool(self.success),
        }


class BaseTool(ABC):
    """Base class for all tools."""
    
    @property
    @abstractmethod
    def tool_id(self) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def schema(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        pass


class EchoTool(BaseTool):
    """A tool that returns the input string unchanged."""
    
    @property
    def tool_id(self) -> str:
        return "echo"
        
    @property
    def name(self) -> str:
        return "echo"
        
    @property
    def description(self) -> str:
        return "Echoes the input back to verify tool calls are working."
        
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to echo"}
            },
            "required": ["text"]
        }

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        text = params.get("text")
        if text is None:
            return ToolResult(success=False, error="Missing required param: 'text'")
        return ToolResult(success=True, output={"echoed": str(text)})


class ShellTool(BaseTool):
    """Tool for executing shell commands safely."""
    
    DEFAULT_TIMEOUT = 30
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT, allow_dangerous: bool = False):
        self._timeout = timeout
        self._allow_dangerous = allow_dangerous
    
    @property
    def tool_id(self) -> str:
        return "shell"
    
    @property
    def name(self) -> str:
        return "shell"
    
    @property
    def description(self) -> str:
        return "Execute Linux shell commands. Do NOT run interactive commands."
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "description": f"Timeout in seconds (default {self.DEFAULT_TIMEOUT})", "default": self.DEFAULT_TIMEOUT},
                "cwd": {"type": "string", "description": "Working directory for command"}
            },
            "required": ["command"]
        }
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        if "command" not in params:
            return ToolResult(success=False, error="Missing required parameter: command")
        
        command = params["command"]
        timeout = params.get("timeout", self._timeout)
        cwd = params.get("cwd")
        
        if not isinstance(command, str) or not command.strip():
            return ToolResult(success=False, error="Command must be a non-empty string")
        
        try:
            result = await asyncio.wait_for(self._run_command(command, cwd), timeout=timeout)
            return result
        except asyncio.TimeoutError:
            return ToolResult(success=False, error=f"Command timed out after {timeout} seconds")
        except Exception as e:
            return ToolResult(success=False, error=f"Error executing command: {str(e)}")
    
    async def _run_command(self, command: str, cwd: Optional[str] = None) -> ToolResult:
        loop = asyncio.get_event_loop()
        
        def run():
            argv = shlex.split(command)
            return subprocess.run(argv, shell=False, capture_output=True, text=True, cwd=cwd, stdin=subprocess.DEVNULL)
        
        proc = await loop.run_in_executor(None, run)
        return ToolResult(
            success=proc.returncode == 0,
            output={
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode
            }
        )


class FileReadTool(BaseTool):
    """Tool for reading file contents and directory listings."""
    
    def __init__(self, base_dir: str = "."):
        self._base_dir = Path(base_dir).resolve()
        if not self._base_dir.exists():
            raise ValueError(f"Base directory does not exist: {base_dir}")

    @property
    def tool_id(self) -> str: return "file_read"
    
    @property
    def name(self) -> str: return "file_read"
    
    @property
    def description(self) -> str: return "Read file contents, list directories, or check existence safely."
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["read", "list_dir", "exists"], "description": "Operation to perform"},
                "path": {"type": "string", "description": "File or directory path"},
                "encoding": {"type": "string", "description": "Encoding for reads", "default": "utf-8"}
            },
            "required": ["operation", "path"]
        }

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        op, path = params.get("operation"), params.get("path")
        if not op or not path:
            return ToolResult(success=False, error="Missing operation or path")
            
        try:
            full_path = (self._base_dir / path).resolve()
            full_path.relative_to(self._base_dir) # Sandbox check
        except ValueError:
            return ToolResult(success=False, error="Path resolves outside sandbox")

        try:
            if op == "exists":
                exists = full_path.exists()
                return ToolResult(success=True, output={
                    "exists": exists, 
                    "is_file": full_path.is_file() if exists else False,
                    "is_dir": full_path.is_dir() if exists else False
                })
            elif op == "list_dir":
                if not full_path.is_dir(): return ToolResult(success=False, error="Not a directory")
                items = [{"name": p.name, "is_dir": p.is_dir()} for p in full_path.iterdir()]
                return ToolResult(success=True, output={"items": items})
            elif op == "read":
                if not full_path.is_file(): return ToolResult(success=False, error="Not a file")
                try:
                    content = full_path.read_text(encoding=params.get("encoding", "utf-8"))
                    return ToolResult(success=True, output={"content": content, "size": len(content), "binary": False})
                except UnicodeDecodeError:
                    size = full_path.stat().st_size
                    return ToolResult(success=False, error="File appears to be binary or not decodable with requested encoding", metadata={"size": size, "binary": True})
            else:
                return ToolResult(success=False, error=f"Unknown operation: {op}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileWriteTool(BaseTool):
    """Tool for writing, appending, or deleting files."""
    
    def __init__(self, base_dir: str = "."):
        self._base_dir = Path(base_dir).resolve()
        if not self._base_dir.exists():
            raise ValueError(f"Base directory does not exist: {base_dir}")

    @property
    def tool_id(self) -> str: return "file_write"
    
    @property
    def name(self) -> str: return "file_write"
    
    @property
    def description(self) -> str: return "Write, append, or delete files safely."
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["write", "append", "delete"], "description": "Operation to perform"},
                "path": {"type": "string", "description": "File or directory path"},
                "content": {"type": "string", "description": "Content for write/append operations"},
                "encoding": {"type": "string", "description": "Encoding for writes", "default": "utf-8"}
            },
            "required": ["operation", "path"]
        }

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        op, path = params.get("operation"), params.get("path")
        if not op or not path:
            return ToolResult(success=False, error="Missing operation or path")
            
        try:
            full_path = (self._base_dir / path).resolve()
            full_path.relative_to(self._base_dir) # Sandbox check
        except ValueError:
            return ToolResult(success=False, error="Path resolves outside sandbox")

        enc = params.get("encoding", "utf-8")
        try:
            if op == "write":
                content = params.get("content", "")
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding=enc)
                return ToolResult(success=True, output={"message": "File written successfully", "bytes": len(content)})
            elif op == "append":
                content = params.get("content", "")
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, "a", encoding=enc) as f:
                    f.write(content)
                return ToolResult(success=True, output={"message": "File appended successfully"})
            elif op == "delete":
                if not full_path.exists():
                    return ToolResult(success=False, error="Path not found")
                if full_path.is_file():
                    full_path.unlink()
                else:
                    full_path.rmdir() # Only empty dirs
                return ToolResult(success=True, output={"message": "Path deleted successfully"})
            else:
                return ToolResult(success=False, error=f"Unknown operation: {op}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SystemInfoTool(BaseTool):
    """Tool for fetching basic system telemetry."""
    
    @property
    def tool_id(self) -> str: return "system_info"
    
    @property
    def name(self) -> str: return "system_info"
    
    @property
    def description(self) -> str: return "Retrieve CPU, Memory, Disk, and OS information."
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "enum": ["all", "cpu", "memory", "disk", "os"], "description": "Specific metric to fetch", "default": "all"}
            }
        }

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        metric = params.get("metric", "all")
        info = {}
        
        try:
            if metric in ["all", "os"]:
                info["os"] = {
                    "system": platform.system(),
                    "release": platform.release(),
                    "machine": platform.machine()
                }
            
            if metric in ["all", "disk"]:
                total, used, free = shutil.disk_usage("/")
                info["disk"] = {
                    "total_gb": round(total / (2**30), 2),
                    "used_gb": round(used / (2**30), 2),
                    "free_gb": round(free / (2**30), 2),
                    "percent_used": round(used / total * 100, 2)
                }
                
            if metric in ["all", "cpu"]:
                info["cpu"] = {
                    "cores": os.cpu_count()
                }
                # Fallback to shell command for linux loadavg
                if platform.system() == "Linux":
                    try:
                        with open("/proc/loadavg", "r") as f:
                            info["cpu"]["loadavg"] = f.read().strip()
                    except: pass
            
            if metric in ["all", "memory"]:
                if platform.system() == "Linux":
                    try:
                        with open("/proc/meminfo", "r") as f:
                            mem = {}
                            for line in f.readlines():
                                if "MemTotal:" in line: mem["total_mb"] = int(line.split()[1]) // 1024
                                if "MemAvailable:" in line: mem["available_mb"] = int(line.split()[1]) // 1024
                            if mem:
                                info["memory"] = mem
                    except: pass
                    
            return ToolResult(success=True, output=info)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
