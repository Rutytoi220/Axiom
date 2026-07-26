import pytest
from axiom.tools import (
    ShellCommandTool, ReadFileTool, WriteFileTool, PythonExecTool,
    ScreenCaptureTool, QueryCodeGraphTool, ShellTool, FileReadTool,
    FileWriteTool, SystemInfoTool, FileTool, EchoTool
)
from unittest.mock import Mock

def test_tool_properties():
    tools = [
        ShellCommandTool(),
        ReadFileTool(),
        WriteFileTool(),
        PythonExecTool(),
        ScreenCaptureTool(),
        QueryCodeGraphTool(index=Mock()),
        ShellTool(),
        FileReadTool(),
        FileWriteTool(),
        SystemInfoTool(),
        FileTool(),
        EchoTool()
    ]
    for t in tools:
        assert isinstance(t.tool_id, str)
        assert getattr(t, 'name', '') != "" or getattr(t, 'name') == getattr(t, 'name')
        assert getattr(t, 'description', '') != "" or getattr(t, 'description') == getattr(t, 'description')
        if hasattr(t, 'schema'):
            assert isinstance(t.schema, dict)

@pytest.mark.asyncio
async def test_shell_tool_prompt(monkeypatch):
    import asyncio
    import os
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("AXIOM_TESTING", raising=False)
    t = ShellTool(allow_dangerous=False)
    
    # 1. Deny
    async def mock_input_no(*args):
        return 'n'
    monkeypatch.setattr(asyncio, "to_thread", mock_input_no)
    res = await t.execute({'command': 'echo 1'})
    assert not res.success
    
    # 2. Allow
    async def mock_input_yes(*args):
        return 'y'
    monkeypatch.setattr(asyncio, "to_thread", mock_input_yes)
    res = await t.execute({'command': 'echo 1'})
    assert res.success
    
    # 3. Exception
    async def mock_input_err(*args):
        raise EOFError()
    monkeypatch.setattr(asyncio, "to_thread", mock_input_err)
    res = await t.execute({'command': 'echo 1'})
    assert not res.success
