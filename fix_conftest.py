import re

with open('tests/conftest.py', 'r') as f:
    content = f.read()

mock_block = """    # 4. Block Model Config Initialization to prevent CLI stall
    try:
        import axiom.core.config_service
        monkeypatch.setattr(axiom.core.config_service, "initialize_model_config", lambda *args, **kwargs: None)
    except ImportError:
        pass
"""

content = content.replace(
    '    # 3. Block urllib.request',
    mock_block + '\n    # 3. Block urllib.request'
)

with open('tests/conftest.py', 'w') as f:
    f.write(content)
