import ast
from pathlib import Path
import sys

target_dir = Path("axiom/gui")
errors = 0
for filepath in target_dir.rglob("*.py"):
    if filepath.is_file():
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            ast.parse(content, filename=str(filepath))
        except Exception as e:
            print(f"Syntax Error in {filepath}: {e}")
            errors += 1

if errors > 0:
    print(f"Failed: {errors} files have syntax errors.")
    sys.exit(1)
else:
    print("Success: 0 syntax errors found.")
