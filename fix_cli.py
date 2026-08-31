with open('tests/unit/test_cli.py', 'r') as f:
    content = f.read()

content = content.replace('assert "nxbt" in captured.out', 'assert "automation" in captured.out')
content = content.replace('assert "nxbt_plugin" in plugins', 'assert "automation" in plugins')

with open('tests/unit/test_cli.py', 'w') as f:
    f.write(content)
