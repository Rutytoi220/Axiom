import re
from pathlib import Path

files_to_check = [
    "axiom/gui/widgets/modern_sidebar.py",
    "axiom/gui/widgets/modern_chat.py",
    "axiom/gui/widgets/scheduler_dialog.py",
    "axiom/gui/widgets/sandbox_container.py"
]

for filepath in files_to_check:
    path = Path(filepath)
    if not path.exists(): continue
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    orig = content
    
    # Strip hardcoded fixed heights on buttons
    content = re.sub(r'self\.\w+_btn\.setFixedHeight\(\d+\)\n?', '', content)
    # Strip hardcoded fixed sizes on buttons
    content = re.sub(r'self\.\w+_btn\.setFixedSize\(\d+,\s*\d+\)\n?', '', content)
    # Generic btn
    content = re.sub(r'btn\.setFixedSize\(\d+,\s*\d+\)\n?', '', content)
    
    if orig != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed scaling in {path.name}")
