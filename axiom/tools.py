"""Tool system for AXIOM."""

import asyncio
import logging
import subprocess
import os
import shlex
import platform
import shutil
from abc import ABC
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


class ToolParameter:
    """Parameter definition for a tool."""
    def __init__(self, name: str, type: str, description: str, required: bool = True, default: Any = None):
        self.name = name
        self.type = type
        self.description = description
        self.required = required
        self.default = default


class BaseTool(ABC):
    """Base class for all tools."""
    
    def __init__(self, tool_id: str = None, name: str = None, description: str = None):
        self._tool_id = tool_id
        self._name = name
        self._description = description
        self.parameters: List[ToolParameter] = []
        self._execution_count = 0

    @property
    def tool_id(self) -> str:
        return self._tool_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def schema(self) -> Dict[str, Any]:
        if hasattr(self, "parameters") and self.parameters:
            properties = {}
            required = []
            for p in self.parameters:
                properties[p.name] = {"type": p.type, "description": p.description}
                if p.required:
                    required.append(p.name)
            return {
                "type": "object",
                "properties": properties,
                "required": required
            }
        return {}

    def add_parameter(self, param: ToolParameter) -> None:
        self.parameters.append(param)

    def get_info(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "description": self.description,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default
                }
                for p in self.parameters
            ],
            "execution_count": self._execution_count
        }

    def validate_parameters(self, **kwargs) -> bool:
        if not hasattr(self, "parameters") or not self.parameters:
            return True
        required_params = {p.name for p in self.parameters if p.required}
        provided_params = set(kwargs.keys())
        if not required_params.issubset(provided_params):
            missing = required_params - provided_params
            logger.error(f"Missing required parameters: {missing}")
            return False
        return True

    def __call__(self, *args, **kwargs) -> ToolResult:
        """Invoke the tool, adapting kwargs to whichever calling convention
        ``execute`` uses (a single ``params``/``arguments`` dict, or explicit
        keyword arguments), and bridging async ``execute`` implementations
        onto a synchronous return value.

        The single-dict-parameter adaptation is determined purely from the
        ``execute`` signature and applies whether ``execute`` is sync or
        async, so callers do not need to know a tool's implementation style.
        """
        self._execution_count += 1

        if hasattr(self, "parameters") and self.parameters:
            if not self.validate_parameters(**kwargs):
                return ToolResult(
                    success=False,
                    output=None,
                    error="Invalid parameters"
                )

        import inspect
        import asyncio

        sig = inspect.signature(self.execute)
        params_list = list(sig.parameters.values())
        single_dict_param = len(params_list) == 1 and (
            params_list[0].annotation == Dict[str, Any]
            or params_list[0].name in ("params", "arguments", "kwargs")
        )
        if single_dict_param:
            execute_args = args if args else (kwargs,)
            execute_kwargs = {}
        else:
            execute_args = args
            execute_kwargs = kwargs

        result = self.execute(*execute_args, **execute_kwargs)
        if not asyncio.iscoroutine(result):
            return result

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                new_loop = asyncio.new_event_loop()
                try:
                    return new_loop.run_until_complete(result)
                finally:
                    new_loop.close()
            else:
                return loop.run_until_complete(result)
        except RuntimeError:
            return asyncio.run(result)

    def execute(self, *args, **kwargs) -> ToolResult:
        """Execute the tool implementation."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement execute()")


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

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        text = params.get("text")
        if text is None:
            return ToolResult(success=False, error="Missing required param: 'text'")
        return ToolResult(success=True, output=str(text))


class ShellTool(BaseTool):
    """Tool for executing shell commands safely."""
    
    DEFAULT_TIMEOUT = 30
    
    DEFAULT_BLOCKLIST = ("rm -rf /", "sudo")

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        allow_dangerous: bool = False,
        blocklist: Optional[List[str]] = None,
    ):
        super().__init__()
        self._timeout = timeout
        self._allow_dangerous = allow_dangerous
        self._blocklist = list(self.DEFAULT_BLOCKLIST if blocklist is None else blocklist)
    
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

        if not self._allow_dangerous and self._is_blocked(command):
            return ToolResult(success=False, error="Command blocked by shell safety policy")

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
            return subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
            )
        
        proc = await loop.run_in_executor(None, run)
        return ToolResult(
            success=proc.returncode == 0,
            output={
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode
            },
            error=None if proc.returncode == 0 else f"Command exited with return code {proc.returncode}",
        )

    def add_blocklist_pattern(self, pattern: str) -> None:
        """Add a case-insensitive substring blocked before execution."""
        if not pattern.strip():
            raise ValueError("Blocklist pattern cannot be empty")
        if pattern not in self._blocklist:
            self._blocklist.append(pattern)

    def remove_blocklist_pattern(self, pattern: str) -> None:
        """Remove a configured blocklist pattern when it exists."""
        try:
            self._blocklist.remove(pattern)
        except ValueError:
            pass

    def _is_blocked(self, command: str) -> bool:
        command_lower = command.lower()
        return any(pattern.lower() in command_lower for pattern in self._blocklist)


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


class FileTool(BaseTool):
    """
    Tool for file system operations with path sandboxing.
    
    Features:
    - Read, write, append, delete files
    - List directories
    - Check file existence
    - All operations restricted to a base directory
    """
    
    OPERATIONS = {"read", "write", "append", "delete", "list_dir", "exists"}
    
    def __init__(self, base_dir: str = "."):
        """
        Initialize FileTool.
        
        Args:
            base_dir: Base directory for all file operations (sandboxing root)
        """
        super().__init__()
        self._base_dir = Path(base_dir).resolve()
        if not self._base_dir.exists():
            raise ValueError(f"Base directory does not exist: {base_dir}")
    
    @property
    def tool_id(self) -> str:
        """Return tool identifier."""
        return "file"
    
    @property
    def name(self) -> str:
        """Return tool name."""
        return "file"
    
    @property
    def description(self) -> str:
        """Return tool description."""
        return "File system operations with path sandboxing"
    
    @property
    def schema(self) -> Dict[str, Any]:
        """Return input schema."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": list(self.OPERATIONS),
                    "description": "File operation to perform"
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path (relative to base_dir)"
                },
                "content": {
                    "type": "string",
                    "description": "Content for write/append operations"
                },
                "encoding": {
                    "type": "string",
                    "description": "File encoding (default utf-8)",
                    "default": "utf-8"
                }
            },
            "required": ["operation", "path"]
        }
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """
        Execute file operation.
        
        Args:
            params: Dict with operation, path, and operation-specific params
        
        Returns:
            ToolResult with operation output
        """
        if "operation" not in params:
            return ToolResult(
                success=False,
                error="Missing required parameter: operation"
            )
        
        if "path" not in params:
            return ToolResult(
                success=False,
                error="Missing required parameter: path"
            )
        
        operation = params["operation"]
        path = params["path"]
        
        if operation not in self.OPERATIONS:
            return ToolResult(
                success=False,
                error=f"Unknown operation: {operation}. Valid operations: {self.OPERATIONS}"
            )
        
        try:
            # Verify path is within sandbox
            file_path = self._resolve_path(path)
            
            if operation == "read":
                return self._read(file_path, params.get("encoding", "utf-8"))
            elif operation == "write":
                if "content" not in params:
                    return ToolResult(
                        success=False,
                        error="write operation requires 'content' parameter"
                    )
                return self._write(file_path, params["content"], params.get("encoding", "utf-8"))
            elif operation == "append":
                if "content" not in params:
                    return ToolResult(
                        success=False,
                        error="append operation requires 'content' parameter"
                    )
                return self._append(file_path, params["content"], params.get("encoding", "utf-8"))
            elif operation == "delete":
                return self._delete(file_path)
            elif operation == "list_dir":
                return self._list_dir(file_path)
            elif operation == "exists":
                return self._exists(file_path)
        
        except ValueError as e:
            return ToolResult(
                success=False,
                error=str(e)
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error during {operation}: {str(e)}"
            )
    
    def _resolve_path(self, relative_path: str) -> Path:
        """
        Resolve relative path and verify it's within sandbox.
        
        Args:
            relative_path: Path relative to base_dir
        
        Returns:
            Resolved absolute Path
        
        Raises:
            ValueError: If path escapes sandbox
        """
        # Resolve the path relative to base_dir
        full_path = (self._base_dir / relative_path).resolve()
        
        # Verify it's within sandbox
        try:
            full_path.relative_to(self._base_dir)
        except ValueError:
            raise ValueError(
                f"Path escape detected: {relative_path} resolves outside sandbox"
            )
        
        return full_path
    
    def _read(self, file_path: Path, encoding: str) -> ToolResult:
        """Read file contents."""
        try:
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"File not found: {file_path.name}"
                )
            
            if not file_path.is_file():
                return ToolResult(
                    success=False,
                    error=f"Not a file: {file_path.name}"
                )
            
            content = file_path.read_text(encoding=encoding)
            return ToolResult(
                success=True,
                output=content,
                metadata={"size": len(content), "encoding": encoding}
            )
        except UnicodeDecodeError as e:
            return ToolResult(
                success=False,
                error=f"Encoding error: {str(e)}"
            )
    
    def _write(self, file_path: Path, content: str, encoding: str) -> ToolResult:
        """Write content to file (overwrite if exists)."""
        try:
            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_path.write_text(content, encoding=encoding)
            return ToolResult(
                success=True,
                output=f"Wrote {len(content)} characters to {file_path.name}",
                metadata={"bytes_written": len(content.encode(encoding)), "encoding": encoding}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Write failed: {str(e)}"
            )
    
    def _append(self, file_path: Path, content: str, encoding: str) -> ToolResult:
        """Append content to file."""
        try:
            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Read existing content if file exists
            if file_path.exists():
                existing = file_path.read_text(encoding=encoding)
                new_content = existing + content
            else:
                new_content = content
            
            file_path.write_text(new_content, encoding=encoding)
            return ToolResult(
                success=True,
                output=f"Appended {len(content)} characters to {file_path.name}",
                metadata={"bytes_appended": len(content.encode(encoding)), "encoding": encoding}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Append failed: {str(e)}"
            )
    
    def _delete(self, file_path: Path) -> ToolResult:
        """Delete file or directory."""
        try:
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Path not found: {file_path.name}"
                )
            
            if file_path.is_file():
                file_path.unlink()
                return ToolResult(
                    success=True,
                    output=f"Deleted file: {file_path.name}"
                )
            elif file_path.is_dir():
                # Only delete empty directories
                try:
                    file_path.rmdir()
                    return ToolResult(
                        success=True,
                        output=f"Deleted directory: {file_path.name}"
                    )
                except OSError:
                    return ToolResult(
                        success=False,
                        error=f"Directory not empty: {file_path.name}"
                    )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Delete failed: {str(e)}"
            )
    
    def _list_dir(self, file_path: Path) -> ToolResult:
        """List directory contents."""
        try:
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Directory not found: {file_path.name}"
                )
            
            if not file_path.is_dir():
                return ToolResult(
                    success=False,
                    error=f"Not a directory: {file_path.name}"
                )
            
            entries = []
            for item in sorted(file_path.iterdir()):
                entry = {
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None
                }
                entries.append(entry)
            
            return ToolResult(
                success=True,
                output=entries,
                metadata={"count": len(entries)}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"List failed: {str(e)}"
            )
    
    def _exists(self, file_path: Path) -> ToolResult:
        """Check if path exists."""
        try:
            exists = file_path.exists()
            is_file = file_path.is_file() if exists else None
            is_dir = file_path.is_dir() if exists else None
            
            return ToolResult(
                success=True,
                output={
                    "exists": exists,
                    "is_file": is_file,
                    "is_dir": is_dir,
                    "path": str(file_path.relative_to(self._base_dir))
                },
                metadata={"exists": exists}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Exists check failed: {str(e)}"
            )
    
    @property
    def base_dir(self) -> Path:
        """Get the sandbox base directory."""
        return self._base_dir


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
