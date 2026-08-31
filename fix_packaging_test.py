import re
with open('tests/unit/test_packaging.py', 'r') as f:
    content = f.read()

content = content.replace('f.write("/sbin/ldconfig() { return 0; }\\n")', 'f.write("/sbin/ldconfig() { return 0; }\\ncommand() { return 1; }\\n")')

with open('tests/unit/test_packaging.py', 'w') as f:
    f.write(content)
