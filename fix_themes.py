import json
from pathlib import Path
from axiom.gui.styles.schema import ThemeTokens

themes_dir = Path("axiom/gui/styles/themes")

# Get defaults from ThemeTokens
default_tokens = ThemeTokens().model_dump()

for theme_path in themes_dir.glob("*.json"):
    with open(theme_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Update tokens
    current_tokens = data.get("tokens", {})
    new_tokens = default_tokens.copy()
    new_tokens.update(current_tokens)
    data["tokens"] = new_tokens
    
    with open(theme_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"Updated {theme_path.name}")

