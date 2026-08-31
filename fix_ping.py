with open('tests/integration/test_sandbox.py', 'r') as f:
    content = f.read()

content = content.replace('"ping", "-c", "1", "127.0.0.1"', '"ping", "-c", "1", "8.8.8.8"')
content = content.replace('touch /etc/sandbox_test_file', 'touch /etc/sandbox_test')

with open('tests/integration/test_sandbox.py', 'w') as f:
    f.write(content)
