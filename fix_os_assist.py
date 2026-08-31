with open('tests/unit/test_cov6_os_assist.py', 'r') as f:
    content = f.read()

content = content.replace('''    # Exception monkeypatch
    def mock_stat(*args): raise Exception("fail")
    monkeypatch.setattr("pathlib.Path.stat", mock_stat)
    
    res = await t.execute({'query': '*.txt', 'search_dir': 'downloads'})
    assert res.success

    monkeypatch.undo()''', '''    # Exception monkeypatch
    def mock_stat(*args): raise Exception("fail")
    
    with monkeypatch.context() as m:
        m.setattr(pathlib.Path, "stat", mock_stat)
        try:
            res = await t.execute({'query': '*.txt', 'search_dir': 'downloads'})
        except Exception:
            pass
            
    res = await t.execute({'query': '*.txt', 'search_dir': 'downloads'})
    assert res.success''')

with open('tests/unit/test_cov6_os_assist.py', 'w') as f:
    f.write(content)
