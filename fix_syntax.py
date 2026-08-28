import os

for root, _, files in os.walk('tests'):
    for file in files:
        if not file.endswith('.py'): continue
        path = os.path.join(root, file)
        with open(path, 'r') as f:
            lines = f.readlines()
        
        # 1. find and remove all `pytestmark = ...` and `import pytest` inserted by me blindly at the top.
        # Actually it's easier to just pull out `from __future__ import annotations` and put it at the absolute top.
        future_idx = -1
        for i, line in enumerate(lines):
            if 'from __future__ import' in line:
                future_idx = i
                break
                
        if future_idx > 0:
            future_line = lines.pop(future_idx)
            lines.insert(0, future_line)
            
        # 2. ensure `import pytest` is before `pytestmark`
        pytest_idx = -1
        mark_idx = -1
        for i, line in enumerate(lines):
            if line.strip() == 'import pytest':
                pytest_idx = i
            if line.startswith('pytestmark = '):
                mark_idx = i
                
        if mark_idx != -1 and (pytest_idx == -1 or mark_idx < pytest_idx):
            # we need to make sure import pytest is before mark_idx
            lines.insert(mark_idx, 'import pytest\n')

        with open(path, 'w') as f:
            f.writelines(lines)
