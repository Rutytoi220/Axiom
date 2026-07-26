import pytest
from axiom.tools import (
    FileReadTool, FileWriteTool, SystemInfoTool, FileTool
)
import platform
import os
import shutil

@pytest.mark.asyncio
async def test_file_read_tool_binary(tmp_path):
    t = FileReadTool(str(tmp_path))
    p = tmp_path / "binary.bin"
    p.write_bytes(b"\x80\x81\x82")
    res = await t.execute({'operation': 'read', 'path': 'binary.bin'})
    assert not res.success

@pytest.mark.asyncio
async def test_file_write_tool_exception(tmp_path, monkeypatch):
    t = FileWriteTool(str(tmp_path))
    
    def mock_unlink(*args, **kwargs):
        raise Exception("unlink fail")
    monkeypatch.setattr("pathlib.Path.unlink", mock_unlink)
    
    p = tmp_path / "test.txt"
    p.touch()
    res = await t.execute({'operation': 'delete', 'path': 'test.txt'})
    assert not res.success

@pytest.mark.asyncio
async def test_system_info_tool_exception(monkeypatch):
    t = SystemInfoTool()
    import builtins
    real_open = builtins.open
    def mock_open(*args, **kwargs):
        raise Exception("open fail")
    monkeypatch.setattr(builtins, "open", mock_open)
    res = await t.execute({'metric': 'all'})
    assert res.success

@pytest.mark.asyncio
async def test_file_tool_complete(tmp_path, monkeypatch):
    t = FileTool(str(tmp_path))
    
    # Write
    res = await t.execute({'operation': 'write', 'path': 'test.txt', 'content': 'hi'})
    assert res.success
    
    # Read
    res = await t.execute({'operation': 'read', 'path': 'test.txt'})
    assert res.success and 'hi' in res.output
    
    # Read binary fail
    p = tmp_path / "binary.bin"
    p.write_bytes(b"\x80\x81\x82")
    res = await t.execute({'operation': 'read', 'path': 'binary.bin'})
    assert not res.success
    
    # Read not file
    (tmp_path / "dir").mkdir(exist_ok=True)
    res = await t.execute({'operation': 'read', 'path': 'dir'})
    assert not res.success
    
    # Read not found
    res = await t.execute({'operation': 'read', 'path': 'nope.txt'})
    assert not res.success
    
    # Read docx
    res = await t.execute({'operation': 'read', 'path': 'test.docx'})
    assert not res.success
    
    # Append
    res = await t.execute({'operation': 'append', 'path': 'test.txt', 'content': ' there'})
    assert res.success
    
    res = await t.execute({'operation': 'append', 'path': 'new.txt', 'content': 'new'})
    assert res.success
    
    # Append fail
    def mock_mkdir(*args, **kwargs): raise Exception("fail")
    monkeypatch.setattr("pathlib.Path.mkdir", mock_mkdir)
    res = await t.execute({'operation': 'append', 'path': 'fail.txt', 'content': 'x'})
    assert not res.success
    
    # Write fail
    res = await t.execute({'operation': 'write', 'path': 'fail.txt', 'content': 'x'})
    assert not res.success
    monkeypatch.undo()
    
    # List dir
    res = await t.execute({'operation': 'list_dir', 'path': ''})
    assert res.success
    
    res = await t.execute({'operation': 'list_dir', 'path': 'nope'})
    assert not res.success
    
    res = await t.execute({'operation': 'list_dir', 'path': 'test.txt'})
    assert not res.success
    
    def mock_iterdir(*args, **kwargs): raise Exception("fail")
    monkeypatch.setattr("pathlib.Path.iterdir", mock_iterdir)
    res = await t.execute({'operation': 'list_dir', 'path': ''})
    assert not res.success
    monkeypatch.undo()
    
    # Delete
    res = await t.execute({'operation': 'delete', 'path': 'test.txt'})
    assert res.success
    
    res = await t.execute({'operation': 'delete', 'path': 'nope'})
    assert not res.success
    
    (tmp_path / "dir2").mkdir(exist_ok=True)
    (tmp_path / "dir2" / "file").touch()
    res = await t.execute({'operation': 'delete', 'path': 'dir2'})
    assert not res.success
    
    def mock_exists(*args, **kwargs): raise Exception("fail")
    monkeypatch.setattr("pathlib.Path.exists", mock_exists)
    res = await t.execute({'operation': 'delete', 'path': 'new.txt'})
    assert not res.success
    monkeypatch.undo()
    
    # Exists
    res = await t.execute({'operation': 'exists', 'path': 'new.txt'})
    assert res.success
    
    monkeypatch.setattr("pathlib.Path.exists", mock_exists)
    res = await t.execute({'operation': 'exists', 'path': 'new.txt'})
    assert not res.success
    
    # Global catch
    monkeypatch.setattr(t, "_exists", mock_exists)
    res = await t.execute({'operation': 'exists', 'path': 'new.txt'})
    assert not res.success
    
    # Property
    assert t.base_dir.name == tmp_path.name
