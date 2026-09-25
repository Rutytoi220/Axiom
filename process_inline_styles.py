import re
import os
from pathlib import Path

target_dir = Path("axiom/gui")
count = 0
for filepath in target_dir.rglob("*.py"):
    if filepath.is_file():
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        matches = re.finditer(r"\.setStyleSheet\((.*?)\)", content, re.DOTALL)
        for m in matches:
            style_str = m.group(1).strip()
            print(f"[{filepath.name}] -> {style_str[:60]}...")
            count += 1
print(f"Total: {count}")
