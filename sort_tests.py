import os
import shutil

os.makedirs('tests/unit', exist_ok=True)
os.makedirs('tests/integration', exist_ok=True)
os.makedirs('tests/gui', exist_ok=True)
os.makedirs('tests/e2e', exist_ok=True)

for root, _, files in os.walk('tests'):
    if 'fixtures' in root or 'optional' in root or 'unit' in root or 'integration' in root or 'gui' in root or 'e2e' in root:
        continue
    for file in files:
        if file.startswith('test_') and file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r') as f:
                content = f.read()
            
            dest = 'unit'
            marker = None
            
            if 'PySide6' in content or 'qtbot' in content or 'qapp' in content:
                dest = 'gui'
                marker = 'gui'
            elif 'e2e' in file.lower() or 'playwright' in file.lower() or 'chaos' in file.lower() or 'system_stress' in file.lower():
                dest = 'e2e'
                marker = 'e2e'
            elif 'websockets' in content or 'fastapi' in content or 'uvicorn' in content or 'daemon' in file.lower() or 'integration' in file.lower() or 'sqlite' in file.lower() or 'database' in content:
                dest = 'integration'
                marker = 'integration'
            
            # move file
            new_path = os.path.join('tests', dest, file)
            shutil.move(path, new_path)
            
            # add marker
            if marker:
                with open(new_path, 'r') as f:
                    content = f.read()
                
                # Check if pytest is imported
                if 'import pytest' not in content:
                    content = 'import pytest\n' + content
                    
                # Add pytestmark
                if f"pytestmark = pytest.mark.{marker}" not in content:
                    # insert after imports
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if not line.startswith('import ') and not line.startswith('from '):
                            lines.insert(i, f"pytestmark = pytest.mark.{marker}")
                            break
                    content = '\n'.join(lines)
                
                with open(new_path, 'w') as f:
                    f.write(content)
