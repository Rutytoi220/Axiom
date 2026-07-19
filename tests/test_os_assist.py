import pytest
from pathlib import Path
from axiom.tools.os_assist import SafeFileSearchTool, FileOpenerTool, AppLauncherTool
import asyncio

@pytest.mark.asyncio
async def test_safe_file_search_traversal_prevention():
    tool = SafeFileSearchTool()
    
    # Path traversal attack
    res = await tool.execute({"query": "../../etc/passwd"})
    assert res.success is False
    assert "blocked" in res.error.lower()
    
    # Absolute path attack
    res = await tool.execute({"query": "/etc/passwd"})
    assert res.success is False
    assert "blocked" in res.error.lower()

@pytest.mark.asyncio
async def test_safe_file_search_invalid_dir():
    tool = SafeFileSearchTool()
    res = await tool.execute({"query": "*.txt", "search_dir": "Windows"})
    assert res.success is False
    assert "permitted safe directory" in res.error

@pytest.mark.asyncio
async def test_safe_file_search_locates_files(tmp_path, monkeypatch):
    tool = SafeFileSearchTool()
    
    # Mock Path.home() to return tmp_path
    def mock_home():
        return tmp_path
    monkeypatch.setattr(Path, "home", mock_home)
    
    # Setup mock user directories
    docs = tmp_path / "Documents"
    docs.mkdir()
    (docs / "test_file.txt").write_text("Hello")
    (docs / "other.pdf").write_text("PDF")
    
    # Test finding files
    res = await tool.execute({"query": "*.txt", "search_dir": "Documents"})
    assert res.success is True
    assert len(res.output) == 1
    assert res.output[0]["name"] == "test_file.txt"

@pytest.mark.asyncio
async def test_app_launcher_safe_mapping():
    tool = AppLauncherTool()
    
    # Invalid app
    res = await tool.execute({"app_name": "malware"})
    assert res.success is False
    assert "Unrecognized safe app" in res.error
    
    # Valid app but we mock subprocess to not actually launch
    import subprocess
    with pytest.MonkeyPatch.context() as m:
        def mock_popen(*args, **kwargs):
            pass
        m.setattr(subprocess, "Popen", mock_popen)
        res = await tool.execute({"app_name": "calculator"})
        assert res.success is True
        assert "Successfully launched calculator" in res.output["message"]
