"""Shell command execution tool for AXIOM."""

import asyncio
import logging
import subprocess
from typing import Any, Dict, List, Optional
from axiom.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ShellTool(BaseTool):
    """
    Tool for executing shell commands safely.
    
    Features:
    - Execute arbitrary shell commands
    - Timeout support to prevent hanging
    - Configurable blocklist for dangerous commands
    - Captures stdout, stderr, and return code
    """
    
    DEFAULT_TIMEOUT = 30
    DEFAULT_BLOCKLIST = [
        "rm -rf /",
        "sudo",
        "sudo rm",
        "dd if=/dev/zero",
        ":(){ :|:& };:",  # Fork bomb
        "mkfs",
        "dd of=/dev",
    ]
    
    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        blocklist: Optional[List[str]] = None,
        allow_dangerous: bool = False
    ):
        """
        Initialize ShellTool.
        
        Args:
            timeout: Command timeout in seconds (default 30)
            blocklist: List of dangerous command patterns to block
            allow_dangerous: If True, bypass blocklist (not recommended)
        """
        self._timeout = timeout
        self._blocklist = blocklist or ([] if allow_dangerous else self.DEFAULT_BLOCKLIST)
        self._allow_dangerous = allow_dangerous
    
    @property
    def tool_id(self) -> str:
        """Return tool identifier."""
        return "shell"
    
    @property
    def name(self) -> str:
        """Return tool name."""
        return "shell"
    
    @property
    def description(self) -> str:
        """Return tool description."""
        return "Execute shell commands with timeout and safety checks"
    
    @property
    def schema(self) -> Dict[str, Any]:
        """Return input schema."""
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": f"Timeout in seconds (default {self.DEFAULT_TIMEOUT})",
                    "default": self.DEFAULT_TIMEOUT,
                    "minimum": 1
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for command"
                }
            },
            "required": ["command"]
        }
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """
        Execute a shell command.
        
        Args:
            params: Dict with "command" (required), "timeout" (optional), "cwd" (optional)
        
        Returns:
            ToolResult with stdout, stderr, returncode
        """
        if "command" not in params:
            return ToolResult(
                success=False,
                error="Missing required parameter: command"
            )
        
        command = params["command"]
        timeout = params.get("timeout", self._timeout)
        cwd = params.get("cwd")
        
        # Check blocklist
        if self._is_blocked(command):
            return ToolResult(
                success=False,
                error=f"Command is blocked for safety reasons: {command}"
            )
        
        try:
            # Run command with timeout using asyncio
            result = await asyncio.wait_for(
                self._run_command(command, cwd),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"Command timed out after {timeout} seconds"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error executing command: {str(e)}"
            )
    
    async def _run_command(self, command: str, cwd: Optional[str] = None) -> ToolResult:
        """
        Run command in subprocess.
        
        Args:
            command: Shell command to run
            cwd: Working directory
        
        Returns:
            ToolResult with output and return code
        """
        loop = asyncio.get_event_loop()
        
        def run():
            return subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd
            )
        
        proc = await loop.run_in_executor(None, run)
        
        success = proc.returncode == 0
        output = {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "returncode": proc.returncode
        }
        
        return ToolResult(
            success=success,
            output=output,
            metadata={"returncode": proc.returncode}
        )
    
    def _is_blocked(self, command: str) -> bool:
        """
        Check if command matches any blocklist patterns.
        
        Args:
            command: Command to check
        
        Returns:
            True if command is blocked
        """
        if self._allow_dangerous:
            return False
        
        for pattern in self._blocklist:
            if pattern in command:
                return True
        
        return False
    
    def add_blocklist_pattern(self, pattern: str) -> None:
        """
        Add a pattern to the blocklist.
        
        Args:
            pattern: String pattern to block
        """
        if pattern not in self._blocklist:
            self._blocklist.append(pattern)
    
    def remove_blocklist_pattern(self, pattern: str) -> None:
        """
        Remove a pattern from the blocklist.
        
        Args:
            pattern: String pattern to unblock
        """
        if pattern in self._blocklist:
            self._blocklist.remove(pattern)
