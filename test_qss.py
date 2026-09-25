import sys
from PySide6.QtWidgets import QApplication
from axiom.gui.styles.theme_manager import get_theme_manager
from axiom.gui.app import _load_stylesheet

app = QApplication(sys.argv)
tm = get_theme_manager()
tm.apply_theme(app, "axiom_pro")
qss = app.styleSheet()
import re
unresolved = re.findall(r'@[a-zA-Z0-9_]+@', qss)
print("Unresolved tokens:", set(unresolved))
