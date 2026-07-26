import pytest
import os
import shutil
import platform
import asyncio
from pathlib import Path
from axiom.tools import (
    ToolResult, ToolParameter, BaseTool, EchoTool,
    ShellTool, FileReadTool, FileWriteTool, SystemInfoTool, FileTool
)

def test_tool_result():
    res = ToolResult(success=False, error="err")
    assert "ToolResult(success=False, error='err')" in repr(res)
    res2 = ToolResult(success=True, output="out")
    assert "ToolResult(success=True, output='out')" in repr(res2)
    d = res2.to_dict(tool="test")
    assert d['tool'] == "test"

class DummyTool(BaseTool):
    def execute(self):
        pass

def test_base_tool():
    t = DummyTool("t", "name", "desc")
    p = ToolParameter("p", "string", "desc", required=True)
    t.add_parameter(p)
    assert t.validate_parameters(p="val")
    assert not t.validate_parameters()
    t.execute = lambda *args, **kwargs: ToolResult(True)
    res = t(p="val")
    assert res.success
    info = t.get_info()
    assert info['tool_id'] == 't'
    
    # Error call
    res2 = t()
    assert not res2.success
    
    # Missing execute
    t2 = BaseTool("t2", "n2", "d2")
    with pytest.raises(NotImplementedError):
        t2.execute()
        
    class AsyncDummy(BaseTool):
        async def execute(self):
            return ToolResult(True)
    ad = AsyncDummy()
    res3 = ad()
    assert res3.success

def test_echo_tool():
    e = EchoTool()
    res = e.execute({})
    assert not res.success
    res = e.execute({'text': 'hi'})
    assert res.success

@pytest.mark.asyncio
async def test_shell_tool(monkeypatch):
    s = ShellTool(allow_dangerous=True)
    res = await s.execute({})
    assert not res.success
    res = await s.execute({'command': ''})
    assert not res.success
    
    # blocked
    s.add_blocklist_pattern("blocked")
    with pytest.raises(ValueError):
        s.add_blocklist_pattern("")
    s.remove_blocklist_pattern("nope")
    res = await s.execute({'command': 'echo blocked'})
    assert not res.success
    
    res = await s.execute({'command': 'echo hi'})
    assert res.success
    
    # Timeout error
    s._timeout = 0.001
    res = await s.execute({'command': 'sleep 1'})
    assert not res.success

@pytest.mark.asyncio
async def test_file_read_tool(tmp_path):
    with pytest.raises(ValueError):
        FileReadTool("/does/not/exist")
        
    f = FileReadTool(str(tmp_path))
    res = await f.execute({})
    assert not res.success
    
    res = await f.execute({'operation': 'read', 'path': '../'})
    assert not res.success
    
    res = await f.execute({'operation': 'exists', 'path': 'nope'})
    assert res.success and not res.output['exists']
    
    (tmp_path / "test.pdf").touch()
    res = await f.execute({'operation': 'read', 'path': 'test.pdf'})
    assert not res.success
    
    (tmp_path / "dir").mkdir()
    res = await f.execute({'operation': 'list_dir', 'path': 'dir'})
    assert res.success
    
    res = await f.execute({'operation': 'list_dir', 'path': 'test.pdf'})
    assert not res.success

    res = await f.execute({'operation': 'read', 'path': 'dir'})
    assert not res.success
    
    res = await f.execute({'operation': 'unknown', 'path': 'dir'})
    assert not res.success

@pytest.mark.asyncio
async def test_file_write_tool(tmp_path):
    with pytest.raises(ValueError):
        FileWriteTool("/does/not/exist")
        
    f = FileWriteTool(str(tmp_path))
    res = await f.execute({})
    assert not res.success
    
    res = await f.execute({'operation': 'write', 'path': '../'})
    assert not res.success
    
    res = await f.execute({'operation': 'write', 'path': 'file.txt', 'content': 'a'})
    assert res.success
    
    res = await f.execute({'operation': 'append', 'path': 'file.txt', 'content': 'b'})
    assert res.success
    
    res = await f.execute({'operation': 'delete', 'path': 'nope'})
    assert not res.success
    
    (tmp_path / "dir").mkdir()
    res = await f.execute({'operation': 'delete', 'path': 'dir'})
    assert res.success
    
    res = await f.execute({'operation': 'unknown', 'path': 'file.txt'})
    assert not res.success

@pytest.mark.asyncio
async def test_system_info_tool(monkeypatch):
    s = SystemInfoTool()
    res = await s.execute({'metric': 'all'})
    assert res.success
    
    # Test exceptions
    def mock_usage(*args): raise Exception("disk")
    monkeypatch.setattr(shutil, "disk_usage", mock_usage)
    res = await s.execute({'metric': 'disk'})
    assert not res.success

@pytest.mark.asyncio
async def test_file_tool(tmp_path):
    with pytest.raises(ValueError):
        FileTool("/does/not/exist")
        
    f = FileTool(str(tmp_path))
    res = await f.execute({})
    assert not res.success
    
    res = await f.execute({'operation': 'read'})
    assert not res.success
    
    res = await f.execute({'operation': 'unknown', 'path': 'a'})
    assert not res.success
    
    res = await f.execute({'operation': 'write', 'path': 'a'})
    assert not res.success
    
    res = await f.execute({'operation': 'append', 'path': 'a'})
    assert not res.success
