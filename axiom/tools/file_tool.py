"""File system tool with path sandboxing for AXIOM."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from axiom.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


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
        self._base_dir = Path(base_dir).resolve()
        if not self._base_dir.exists():
            raise ValueError(f"Base directory does not exist: {base_dir}")
    
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
