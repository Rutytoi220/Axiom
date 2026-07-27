import sys
from PySide6.QtWidgets import QApplication
import axiom.gui.app as gui_app
from axiom.config import get_config

app = QApplication(sys.argv)
config = get_config()
config.theme_mode = "light"
gui_app._load_stylesheet(app)
print("Stylesheet set. Length:", len(app.styleSheet()))
