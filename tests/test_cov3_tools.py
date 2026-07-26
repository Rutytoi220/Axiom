import pytest
import os
import shutil
import platform
import asyncio
from pathlib import Path
from axiom.tools import (
    ShellCommandTool, ReadFileTool, WriteFileTool, PythonExecTool,
    ScreenCaptureTool, QueryCodeGraphTool
)
from unittest.mock import Mock

def test_shell_command_tool():
    t = ShellCommandTool()
    res = t(command='')
    res = t(command='echo 1')

def test_read_file_tool(tmp_path):
    t = ReadFileTool()
    p = tmp_path / "test.txt"
    p.write_text("hello")
    res = t(path=str(p))
    res = t(path='../')

def test_write_file_tool(tmp_path):
    t = WriteFileTool()
    p = tmp_path / "test.txt"
    res = t(path=str(p), content='a')

def test_python_exec_tool():
    t = PythonExecTool()
    res = t(code='print(1)')
    res = t(code='import os; os.system("echo 1")')

def test_screen_capture_tool(monkeypatch):
    t = ScreenCaptureTool()
    class MockImage:
        def __init__(self): self.size = (100, 100)
        def save(self, path, format=None, quality=None):
            pass
            
    import builtins
    real_import = builtins.__import__
    def mock_import(name, *args, **kwargs):
        if name == 'pyautogui':
            class MockPyautogui:
                @staticmethod
                def screenshot(): return MockImage()
            return MockPyautogui()
        return real_import(name, *args, **kwargs)
        
    monkeypatch.setattr(builtins, "__import__", mock_import)
    res = t()

    def mock_import_fail(name, *args, **kwargs):
        if name == 'pyautogui': raise ImportError("Fail")
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", mock_import_fail)
    try:
        t()
    except Exception:
        pass

def test_query_code_graph_tool():
    t = QueryCodeGraphTool(index=Mock())
    res = t(query='test')
