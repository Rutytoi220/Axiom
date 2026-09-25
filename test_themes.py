from axiom.gui.styles.theme_registry import ThemeRegistry
from pathlib import Path
registry = ThemeRegistry(Path('axiom/gui/styles/themes'))
registry.discover_themes()
print('Discovered themes:', registry.list_theme_ids())
