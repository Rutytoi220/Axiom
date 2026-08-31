with open('tests/conftest.py', 'r') as f:
    content = f.read()

urllib_mock = """
    # 3. Block urllib.request
    def mock_urlopen(*args, **kwargs):
        raise RuntimeError("Strict Mock: Network IO is blocked via urllib.request.")
    try:
        import urllib.request
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    except ImportError:
        pass
"""

content = content.replace('    # 2. Block LiteLLM Completions', urllib_mock + '\n    # 2. Block LiteLLM Completions')

with open('tests/conftest.py', 'w') as f:
    f.write(content)
