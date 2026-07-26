import pytest
from axiom.tools.os_assist import SafeFileSearchTool, FileOpenerTool, AppLauncherTool
import platform
import pathlib

@pytest.mark.asyncio
async def test_file_search_tool_dir_not_exist(tmp_path, monkeypatch):
    t = SafeFileSearchTool(str(tmp_path))
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
    t.SAFE_DIRS.append('missing')
    res = await t.execute({'query': 'test', 'search_dir': 'missing'})
    assert not res.success

@pytest.mark.asyncio
async def test_file_search_tool_exception(tmp_path, monkeypatch):
    t = SafeFileSearchTool(str(tmp_path))
    t.SAFE_DIRS.append('downloads')
    (tmp_path / 'downloads').mkdir()
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
    
    # Create 50 files
    for i in range(55):
        (tmp_path / 'downloads' / f"{i}.txt").touch()

    # Exception monkeypatch
    def mock_stat(*args): raise Exception("fail")
    monkeypatch.setattr("pathlib.Path.stat", mock_stat)
    
    res = await t.execute({'query': '*.txt', 'search_dir': 'downloads'})
    assert res.success

    monkeypatch.undo()
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
    res = await t.execute({'query': '*.txt', 'search_dir': 'downloads'})
    assert res.success
    assert len(res.output) == 50

@pytest.mark.asyncio
async def test_file_opener_tool_exts(tmp_path, monkeypatch):
    t = FileOpenerTool()
    class MockPopen:
        def __init__(self, *args, **kwargs): pass
    monkeypatch.setattr("subprocess.Popen", MockPopen)
    
    for ext in ['test.docx', 'test.xlsx', 'test.pptx', 'test.zip', 'test.html']:
        p = tmp_path / ext
        p.touch()
        res = await t.execute({'file_path': str(p)})
        assert res.success

@pytest.mark.asyncio
async def test_app_launcher_exception(monkeypatch):
    t = AppLauncherTool()
    def mock_popen(*args, **kwargs): raise Exception("fail")
    monkeypatch.setattr("subprocess.Popen", mock_popen)
    # mock SAFE_APPS
    t.SAFE_APPS['testapp'] = {'Linux': ['testapp']}
    monkeypatch.setattr("platform.system", lambda: 'Linux')
    res = await t.execute({'app_name': 'testapp'})
    assert not res.success
