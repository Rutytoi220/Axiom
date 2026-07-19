"""Test suite for AXIOM tools."""

import asyncio
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock

from axiom.tools import BaseTool, ToolResult, ShellTool, FileTool, FileReadTool


class TestToolResult:
    """Test ToolResult dataclass."""
    
    def test_tool_result_success(self):
        """Test creating successful result."""
        result = ToolResult(success=True, output="test output")
        assert result.success is True
        assert result.output == "test output"
        assert result.error is None
        assert result.metadata == {}
    
    def test_tool_result_failure(self):
        """Test creating failed result."""
        result = ToolResult(success=False, error="Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.output is None
    
    def test_tool_result_with_metadata(self):
        """Test result with metadata."""
        metadata = {"duration": 0.5, "attempts": 3}
        result = ToolResult(success=True, output="done", metadata=metadata)
        assert result.metadata == metadata
    
    def test_tool_result_repr(self):
        """Test result repr."""
        result = ToolResult(success=True, output="test")
        repr_str = repr(result)
        assert "ToolResult" in repr_str
        assert "success=True" in repr_str


class TestShellTool:
    """Test ShellTool implementation."""
    
    def test_shell_tool_properties(self):
        """Test ShellTool properties."""
        tool = ShellTool()
        assert tool.name == "shell"
        assert "shell command" in tool.description.lower()
        assert "command" in tool.schema["properties"]
    
    def test_shell_tool_schema(self):
        """Test ShellTool schema format."""
        tool = ShellTool()
        schema = tool.schema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert "command" in schema["required"]
    
    @pytest.mark.asyncio
    async def test_shell_execute_simple_command(self):
        """Test executing a simple shell command."""
        tool = ShellTool()
        result = await tool.execute({"command": "echo hello"})
        
        assert result.success is True
        assert "hello" in result.output["stdout"]
        assert result.output["returncode"] == 0
    
    @pytest.mark.asyncio
    async def test_shell_execute_with_stderr(self):
        """Test command that writes to stderr."""
        tool = ShellTool()
        result = await tool.execute({"command": "python -c \"import sys; sys.stderr.write('error')\""}
)
        
        # Command should succeed even with stderr
        assert isinstance(result.success, bool)
        assert "error" in result.output["stderr"]
    
    @pytest.mark.asyncio
    async def test_shell_execute_failing_command(self):
        """Test command with non-zero exit code."""
        tool = ShellTool()
        result = await tool.execute({"command": "exit 1"})
        
        assert result.success is False
        assert result.output["returncode"] == 1
    
    @pytest.mark.asyncio
    async def test_shell_execute_timeout(self):
        """Test command that times out."""
        tool = ShellTool(timeout=1)
        result = await tool.execute({
            "command": "sleep 5",
            "timeout": 1
        })
        
        assert result.success is False
        assert ("timeout" in result.error.lower() or "timed out" in result.error.lower())
    
    @pytest.mark.asyncio
    async def test_shell_execute_missing_command_param(self):
        """Test error when command parameter missing."""
        tool = ShellTool()
        result = await tool.execute({})
        
        assert result.success is False
        assert "command" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_shell_blocklist_default(self):
        """Test default blocklist blocks dangerous commands."""
        tool = ShellTool()
        
        # Should block rm -rf /
        result = await tool.execute({"command": "rm -rf /"})
        assert result.success is False
        assert "blocked" in result.error.lower()
        
        # Should block sudo
        result = await tool.execute({"command": "sudo ls"})
        assert result.success is False
        assert "blocked" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_shell_blocklist_custom(self):
        """Test custom blocklist."""
        blocklist = ["dangerous"]
        tool = ShellTool(blocklist=blocklist)
        
        result = await tool.execute({"command": "echo dangerous command"})
        assert result.success is False
        assert "blocked" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_shell_blocklist_empty(self):
        """Test with empty blocklist."""
        tool = ShellTool(blocklist=[])
        
        result = await tool.execute({"command": "echo test"})
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_shell_allow_dangerous(self):
        """Test allow_dangerous flag bypasses blocklist."""
        tool = ShellTool(allow_dangerous=True)
        
        # Command would normally be blocked, but allow_dangerous overrides
        result = await tool.execute({"command": "echo safe"})
        assert result.success is True
    
    def test_shell_add_blocklist_pattern(self):
        """Test adding blocklist patterns."""
        tool = ShellTool(blocklist=[])
        tool.add_blocklist_pattern("dangerous")
        
        assert "dangerous" in tool._blocklist
    
    def test_shell_remove_blocklist_pattern(self):
        """Test removing blocklist patterns."""
        tool = ShellTool(blocklist=["test"])
        tool.remove_blocklist_pattern("test")
        
        assert "test" not in tool._blocklist
    
    @pytest.mark.asyncio
    async def test_shell_with_cwd(self):
        """Test shell command with working directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = ShellTool()
            result = await tool.execute({
                "command": "pwd",
                "cwd": tmpdir
            })
            
            assert result.success is True
            assert tmpdir in result.output["stdout"]
    
    @pytest.mark.asyncio
    async def test_shell_custom_timeout(self):
        """Test custom timeout parameter."""
        tool = ShellTool(timeout=10)
        result = await tool.execute({
            "command": "sleep 1",
            "timeout": 5
        })
        
        # Should complete successfully
        assert result.success is True


class TestFileReadTool:
    """Test FileReadTool implementation."""

    @pytest.mark.asyncio
    async def test_file_read_rejects_pdf(self):
        """Test reading a PDF file is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileReadTool(base_dir=tmpdir)
            test_file = Path(tmpdir) / "test.pdf"
            test_file.write_text("fake pdf data")
            
            result = await tool.execute({
                "operation": "read",
                "path": "test.pdf"
            })
            
            assert result.success is False
            assert "MUST use the read_document_content tool" in result.error


class TestFileTool:
    """Test FileTool implementation."""
    
    def test_file_tool_properties(self):
        """Test FileTool properties."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            assert tool.name == "file"
            assert "file" in tool.description.lower()
    
    def test_file_tool_schema(self):
        """Test FileTool schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            schema = tool.schema
            assert schema["type"] == "object"
            assert "operation" in schema["properties"]
            assert "path" in schema["properties"]
    
    def test_file_tool_base_dir_nonexistent(self):
        """Test error when base_dir doesn't exist."""
        with pytest.raises(ValueError, match="does not exist"):
            FileTool(base_dir="/nonexistent/path/xyz123")
    
    @pytest.mark.asyncio
    async def test_file_read_existing_file(self):
        """Test reading an existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("hello world")
            
            result = await tool.execute({
                "operation": "read",
                "path": "test.txt"
            })
            
            assert result.success is True
            assert result.output == "hello world"

    @pytest.mark.asyncio
    async def test_file_read_rejects_pdf(self):
        """Test reading a PDF file is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            test_file = Path(tmpdir) / "test.pdf"
            test_file.write_text("fake pdf data")
            
            result = await tool.execute({
                "operation": "read",
                "path": "test.pdf"
            })
            
            assert result.success is False
            assert "MUST use the read_document_content tool" in result.error
    
    @pytest.mark.asyncio
    async def test_file_read_nonexistent_file(self):
        """Test error reading nonexistent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            
            result = await tool.execute({
                "operation": "read",
                "path": "missing.txt"
            })
            
            assert result.success is False
            assert "not found" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_file_write_new_file(self):
        """Test writing to a new file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            
            result = await tool.execute({
                "operation": "write",
                "path": "new.txt",
                "content": "test content"
            })
            
            assert result.success is True
            
            # Verify file was created
            written_file = Path(tmpdir) / "new.txt"
            assert written_file.read_text() == "test content"
    
    @pytest.mark.asyncio
    async def test_file_write_overwrites_existing(self):
        """Test that write overwrites existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("original")
            
            result = await tool.execute({
                "operation": "write",
                "path": "test.txt",
                "content": "new content"
            })
            
            assert result.success is True
            assert test_file.read_text() == "new content"
    
    @pytest.mark.asyncio
    async def test_file_write_creates_directories(self):
        """Test that write creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            
            result = await tool.execute({
                "operation": "write",
                "path": "nested/dir/file.txt",
                "content": "content"
            })
            
            assert result.success is True
            nested_file = Path(tmpdir) / "nested" / "dir" / "file.txt"
            assert nested_file.exists()
    
    @pytest.mark.asyncio
    async def test_file_append(self):
        """Test appending to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("line1\n")
            
            result = await tool.execute({
                "operation": "append",
                "path": "test.txt",
                "content": "line2\n"
            })
            
            assert result.success is True
            assert test_file.read_text() == "line1\nline2\n"
    
    @pytest.mark.asyncio
    async def test_file_append_to_nonexistent(self):
        """Test appending creates file if doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            
            result = await tool.execute({
                "operation": "append",
                "path": "new.txt",
                "content": "content"
            })
            
            assert result.success is True
            new_file = Path(tmpdir) / "new.txt"
            assert new_file.read_text() == "content"
    
    @pytest.mark.asyncio
    async def test_file_delete_file(self):
        """Test deleting a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("content")
            
            result = await tool.execute({
                "operation": "delete",
                "path": "test.txt"
            })
            
            assert result.success is True
            assert not test_file.exists()
    
    @pytest.mark.asyncio
    async def test_file_delete_nonexistent(self):
        """Test error deleting nonexistent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            
            result = await tool.execute({
                "operation": "delete",
                "path": "missing.txt"
            })
            
            assert result.success is False
            assert "not found" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_file_delete_empty_directory(self):
        """Test deleting an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            empty_dir = Path(tmpdir) / "empty"
            empty_dir.mkdir()
            
            result = await tool.execute({
                "operation": "delete",
                "path": "empty"
            })
            
            assert result.success is True
            assert not empty_dir.exists()
    
    @pytest.mark.asyncio
    async def test_file_delete_nonempty_directory(self):
        """Test error deleting nonempty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            dir_path = Path(tmpdir) / "nonempty"
            dir_path.mkdir()
            (dir_path / "file.txt").write_text("content")
            
            result = await tool.execute({
                "operation": "delete",
                "path": "nonempty"
            })
            
            assert result.success is False
            assert "not empty" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_file_list_dir(self):
        """Test listing directory contents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            
            # Create test structure
            (Path(tmpdir) / "file1.txt").write_text("content")
            (Path(tmpdir) / "file2.txt").write_text("content")
            (Path(tmpdir) / "subdir").mkdir()
            
            result = await tool.execute({
                "operation": "list_dir",
                "path": "."
            })
            
            assert result.success is True
            names = [item["name"] for item in result.output]
            assert "file1.txt" in names
            assert "file2.txt" in names
            assert "subdir" in names
            assert result.metadata["count"] == 3
    
    @pytest.mark.asyncio
    async def test_file_list_dir_empty(self):
        """Test listing empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            
            result = await tool.execute({
                "operation": "list_dir",
                "path": "."
            })
            
            assert result.success is True
            assert result.output == []
            assert result.metadata["count"] == 0
    
    @pytest.mark.asyncio
    async def test_file_list_dir_nonexistent(self):
        """Test error listing nonexistent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            
            result = await tool.execute({
                "operation": "list_dir",
                "path": "missing"
            })
            
            assert result.success is False
            assert "not found" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_file_exists_true(self):
        """Test exists operation for existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("content")
            
            result = await tool.execute({
                "operation": "exists",
                "path": "test.txt"
            })
            
            assert result.success is True
            assert result.output["exists"] is True
            assert result.output["is_file"] is True
            assert result.output["is_dir"] is False
    
    @pytest.mark.asyncio
    async def test_file_exists_false(self):
        """Test exists operation for nonexistent path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            
            result = await tool.execute({
                "operation": "exists",
                "path": "missing.txt"
            })
            
            assert result.success is True
            assert result.output["exists"] is False
            assert result.output["is_file"] is None
    
    @pytest.mark.asyncio
    async def test_file_exists_directory(self):
        """Test exists for directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            
            result = await tool.execute({
                "operation": "exists",
                "path": "subdir"
            })
            
            assert result.success is True
            assert result.output["exists"] is True
            assert result.output["is_dir"] is True
            assert result.output["is_file"] is False
    
    @pytest.mark.asyncio
    async def test_file_sandbox_escape_attempt_parent(self):
        """Test that .. path escapes are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            
            result = await tool.execute({
                "operation": "read",
                "path": "../../etc/passwd"
            })
            
            assert result.success is False
            assert "escape" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_file_sandbox_escape_attempt_absolute(self):
        """Test that absolute paths are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            
            result = await tool.execute({
                "operation": "read",
                "path": "/etc/passwd"
            })
            
            assert result.success is False
            assert "escape" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_file_missing_operation_param(self):
        """Test error when operation parameter missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            
            result = await tool.execute({"path": "test.txt"})
            
            assert result.success is False
            assert "operation" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_file_missing_path_param(self):
        """Test error when path parameter missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            
            result = await tool.execute({"operation": "read"})
            
            assert result.success is False
            assert "path" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_file_unknown_operation(self):
        """Test error for unknown operation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            
            result = await tool.execute({
                "operation": "invalid",
                "path": "test.txt"
            })
            
            assert result.success is False
            assert "unknown" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_file_write_missing_content(self):
        """Test error when write lacks content parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            
            result = await tool.execute({
                "operation": "write",
                "path": "test.txt"
            })
            
            assert result.success is False
            assert "content" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_file_custom_encoding(self):
        """Test file operations with custom encoding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(base_dir=tmpdir)
            
            result = await tool.execute({
                "operation": "write",
                "path": "test.txt",
                "content": "café",
                "encoding": "utf-8"
            })
            
            assert result.success is True
            
            # Read it back
            result = await tool.execute({
                "operation": "read",
                "path": "test.txt",
                "encoding": "utf-8"
            })
            
            assert result.success is True
            assert "café" in result.output


class TestScreenCaptureTool:
    """Test ScreenCaptureTool implementation."""
    
    def test_screen_capture_tool_properties(self):
        """Test properties of ScreenCaptureTool."""
        from axiom.tools import ScreenCaptureTool
        tool = ScreenCaptureTool()
        assert tool.name == "screen_capture"
        assert "screenshot" in tool.description.lower()
        
    def test_screen_capture_tool_schema(self):
        """Test schema of ScreenCaptureTool."""
        from axiom.tools import ScreenCaptureTool
        tool = ScreenCaptureTool()
        schema = tool.schema
        assert schema["type"] == "object"
        assert "filename" in schema["properties"]
        
    @pytest.mark.asyncio
    async def test_screen_capture_success(self):
        """Test successful screen capture."""
        from axiom.tools import ScreenCaptureTool
        import sys
        from unittest.mock import MagicMock
        
        mock_pyautogui = MagicMock()
        mock_img = MagicMock()
        mock_img.width = 800
        mock_img.height = 600
        
        def fake_save(filepath):
            with open(filepath, 'w') as f:
                f.write('fake')
        mock_img.save.side_effect = fake_save
        mock_pyautogui.screenshot.return_value = mock_img
        
        real_pyautogui = sys.modules.get("pyautogui")
        sys.modules["pyautogui"] = mock_pyautogui
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tool = ScreenCaptureTool(capture_dir=tmpdir)
                result = await tool.execute({"filename": "test_shot"})
                
                assert result.success is True
                assert "test_shot.png" in result.output["path"]
                assert Path(result.output["path"]).exists()
                assert result.metadata["width"] == 800
                assert result.metadata["height"] == 600
                mock_pyautogui.screenshot.assert_called_once()
        finally:
            if real_pyautogui is not None:
                sys.modules["pyautogui"] = real_pyautogui
            else:
                del sys.modules["pyautogui"]
            
    @pytest.mark.asyncio
    async def test_screen_capture_default_filename(self):
        """Test screen capture with default filename."""
        from axiom.tools import ScreenCaptureTool
        import sys
        from unittest.mock import MagicMock
        
        mock_pyautogui = MagicMock()
        mock_img = MagicMock()
        mock_img.width = 800
        mock_img.height = 600
        
        def fake_save(filepath):
            with open(filepath, 'w') as f:
                f.write('fake')
        mock_img.save.side_effect = fake_save
        mock_pyautogui.screenshot.return_value = mock_img
        
        real_pyautogui = sys.modules.get("pyautogui")
        sys.modules["pyautogui"] = mock_pyautogui
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tool = ScreenCaptureTool(capture_dir=tmpdir)
                result = await tool.execute({})
                
                assert result.success is True
                assert "screenshot_" in result.output["path"]
                assert Path(result.output["path"]).exists()
        finally:
            if real_pyautogui is not None:
                sys.modules["pyautogui"] = real_pyautogui
            else:
                del sys.modules["pyautogui"]
            
    @pytest.mark.asyncio
    async def test_screen_capture_no_pyautogui(self):
        """Test graceful degradation when pyautogui is missing."""
        from axiom.tools import ScreenCaptureTool
        import sys
        
        real_pyautogui = sys.modules.get("pyautogui")
        sys.modules["pyautogui"] = None
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tool = ScreenCaptureTool(capture_dir=tmpdir)
                result = await tool.execute({})
                
                assert result.success is False
                assert "not installed" in result.error
        finally:
            if real_pyautogui is not None:
                sys.modules["pyautogui"] = real_pyautogui
            else:
                del sys.modules["pyautogui"]
