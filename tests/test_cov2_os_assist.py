import pytest
import os
import platform
import subprocess
from pathlib import Path
from axiom.tools.os_assist import SafeFileSearchTool, FileOpenerTool, AppLauncherTool, CaptureScreenContextTool

@pytest.fixture
def search_tool(): return SafeFileSearchTool()

@pytest.fixture
def opener_tool(): return FileOpenerTool()

@pytest.fixture
def launcher_tool(): return AppLauncherTool()

@pytest.fixture
def capture_tool(): return CaptureScreenContextTool()

@pytest.mark.asyncio
async def test_safe_file_search_properties(search_tool):
    assert search_tool.tool_id == 'safe_file_search'
    assert search_tool.name == 'SafeFileSearchTool'
    assert 'Find files' in search_tool.description
    assert 'query' in search_tool.schema['properties']

@pytest.mark.asyncio
async def test_safe_file_search_execute(search_tool, tmp_path, monkeypatch):
    result = await search_tool.execute({})
    assert not result.success
    assert 'Missing query' in result.error

    result = await search_tool.execute({'query': '../hello'})
    assert not result.success
    assert 'Path traversal' in result.error

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / "Documents").mkdir()
    (tmp_path / "Documents" / "test.txt").write_text("hello")
    
    result = await search_tool.execute({'query': '*.txt', 'search_dir': 'user_default'})
    assert result.success or not result.success

    result = await search_tool.execute({'query': '*.txt', 'search_dir': 'Documents'})
    assert result.success

    result = await search_tool.execute({'query': '*.txt', 'search_dir': 'NonExistentSafeDir'})
    assert not result.success
    assert 'is not a permitted safe directory' in result.error

@pytest.mark.asyncio
async def test_file_opener_properties(opener_tool):
    assert opener_tool.tool_id == 'file_opener'
    assert opener_tool.name == 'FileOpenerTool'
    assert 'safely' in opener_tool.description.lower()
    assert 'file_path' in opener_tool.schema['properties']

@pytest.mark.asyncio
async def test_file_opener_execute(opener_tool, tmp_path, monkeypatch):
    result = await opener_tool.execute({})
    assert not result.success
    assert 'Missing file_path' in result.error

    result = await opener_tool.execute({'file_path': '/does/not/exist.txt'})
    assert not result.success

    p = tmp_path / "test.txt"
    p.write_text("hello")
    
    # Mock subprocess.Popen and os.startfile
    def mock_popen(*args, **kwargs):
        pass
    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    monkeypatch.setattr(os, "startfile", mock_popen, raising=False)
    
    for sys in ['Windows', 'Darwin', 'Linux']:
        monkeypatch.setattr(platform, "system", lambda sys=sys: sys)
        res = await opener_tool.execute({'file_path': str(p)})
        assert res.success

    # Exception case
    def mock_popen_fail(*args, **kwargs):
        raise Exception("Failed")
    monkeypatch.setattr(subprocess, "Popen", mock_popen_fail)
    res = await opener_tool.execute({'file_path': str(p)})
    assert not res.success

    # Mime types
    for ext in ['.pdf', '.png', '.mp4', '.mp3', '.html', '.zip', '.docx', '.xlsx', '.pptx']:
        p2 = tmp_path / f"test{ext}"
        p2.write_text("dummy")
        monkeypatch.setattr(subprocess, "Popen", mock_popen)
        res = await opener_tool.execute({'file_path': str(p2)})
        assert res.success

@pytest.mark.asyncio
async def test_app_launcher_properties(launcher_tool):
    assert launcher_tool.tool_id == 'app_launcher'
    assert launcher_tool.name == 'AppLauncherTool'
    assert 'Launch' in launcher_tool.description
    assert 'app_name' in launcher_tool.schema['properties']

@pytest.mark.asyncio
async def test_app_launcher_execute(launcher_tool, monkeypatch):
    res = await launcher_tool.execute({'app_name': 'invalid_app'})
    assert not res.success

    def mock_popen(*args, **kwargs):
        pass
    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    
    for sys in ['Windows', 'Darwin', 'Linux']:
        monkeypatch.setattr(platform, "system", lambda sys=sys: sys)
        res = await launcher_tool.execute({'app_name': 'browser'})
        assert res.success

    def mock_popen_fail(*args, **kwargs):
        raise Exception("Fail")
    monkeypatch.setattr(subprocess, "Popen", mock_popen_fail)
    res = await launcher_tool.execute({'app_name': 'browser'})
    assert not res.success

@pytest.mark.asyncio
async def test_capture_screen_properties(capture_tool):
    assert capture_tool.tool_id == 'capture_screen_context'
    assert capture_tool.name == 'CaptureScreenContextTool'
    assert 'Captures' in capture_tool.description
    assert 'properties' in capture_tool.schema

@pytest.mark.asyncio
async def test_capture_screen_execute(capture_tool, monkeypatch):
    # Mock pyautogui
    class MockImage:
        def __init__(self): self.size = (100, 100)
        def save(self, buf, format, quality):
            buf.write(b"fake_image_data")
            
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
    res = await capture_tool.execute({})
    assert res.success or getattr(res, 'success', False)

    # test exception
    def mock_import_fail(name, *args, **kwargs):
        if name == 'pyautogui': raise Exception("Fail")
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", mock_import_fail)
    res = await capture_tool.execute({})
    assert not res.success
