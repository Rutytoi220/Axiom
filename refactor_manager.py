import re

with open('axiom/gui/styles/theme_manager.py', 'r') as f:
    content = f.read()

# Add import for ThemeRegistry
if "from axiom.gui.styles.theme_registry import ThemeRegistry" not in content:
    content = content.replace("from typing import Dict, Any, Optional", "from typing import Dict, Any, Optional\nfrom axiom.gui.styles.theme_registry import ThemeRegistry")

# Replace _load_themes and __init__
replacement_init = """    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._registry = ThemeRegistry(THEMES_DIR)
        self._active_theme_name: str = ""
        self._active_theme_data: Dict[str, Any] = {}
        self._load_themes()

    def _load_themes(self):
        \"\"\"Load all JSON themes securely via ThemeRegistry.\"\"\"
        self._registry.discover_themes()
        # Fallback for old getter logic if needed, but we mostly use self._registry.themes now
"""

content = re.sub(r'    def __init__\(self, parent=None\) -> None:.*?def _load_themes\(self\):.*?logger\.error\(f"Failed to load theme \{json_file\}: \{e\}"\)', replacement_init, content, flags=re.DOTALL)

# In apply_theme, we need to check self._registry.themes instead of self._themes
# and we need to pull 'tokens' instead of the raw data.
# Let's replace the top of apply_theme
apply_theme_logic = """    def apply_theme(self, app: QApplication, theme_name: str = "axiom_pro") -> None:
        \"\"\"Apply a theme globally to the QApplication.\"\"\"
        if theme_name not in self._registry.themes:
            logger.warning(f"Theme '{theme_name}' not found. Falling back to default if available.")
            if not self._registry.themes:
                return
            theme_name = list(self._registry.themes.keys())[0]

        self._active_theme_name = theme_name
        theme_package = self._registry.themes[theme_name]
        self._active_theme_data = theme_package.get("tokens", {})

        if not QSS_TEMPLATE.exists():
            logger.error(f"QSS template not found: {QSS_TEMPLATE}")
            return

        try:
            with open(QSS_TEMPLATE, 'r') as f:
                qss = f.read()

            # Replace tokens
            for key, value in self._active_theme_data.items():
                if isinstance(value, str):
                    qss = qss.replace(f"@{key}@", value)"""

content = re.sub(r'    def apply_theme\(self, app: QApplication, theme_name: str = "axiom_pro"\) -> None:.*?if isinstance\(value, str\):\n                    qss = qss\.replace\(f"@{key}@", value\)', apply_theme_logic, content, flags=re.DOTALL)

with open('axiom/gui/styles/theme_manager.py', 'w') as f:
    f.write(content)
