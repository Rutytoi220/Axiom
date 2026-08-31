with open('tests/gui/test_v57.py', 'r') as f:
    lines = f.readlines()

out = []
in_test = False
for line in lines:
    if line.startswith('import ') or line.startswith('pytestmark') or line.startswith('sys.path'):
        out.append(line)
    elif line.startswith('# 1.'):
        out.append('\ndef test_v57_widgets(qapp):\n')
        out.append('    ' + line)
        in_test = True
    elif in_test:
        out.append('    ' + line)
    else:
        out.append(line)

with open('tests/gui/test_v57.py', 'w') as f:
    f.writelines(out)
