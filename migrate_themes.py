import json
import os
from pathlib import Path

themes_dir = Path('axiom/gui/styles/themes')
for theme_file in themes_dir.glob('*.json'):
    with open(theme_file, 'r') as f:
        data = json.load(f)
    
    if "tokens" in data:
        continue # Already migrated
        
    theme_id = data.pop("name", theme_file.stem)
    new_data = {
        "id": theme_id,
        "name": theme_id.replace("_", " ").title(),
        "author": "AXIOM Team",
        "version": "1.0.0",
        "tokens": data
    }
    
    with open(theme_file, 'w') as f:
        json.dump(new_data, f, indent=4)
        
