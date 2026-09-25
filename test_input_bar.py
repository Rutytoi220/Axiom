import sys
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication
from axiom.gui.app import _load_stylesheet
from axiom.gui.widgets.modern_chat import ModernInputBar

app = QApplication(sys.argv)
from axiom.gui.styles.theme_manager import get_theme_manager
tm = get_theme_manager()
tm.apply_theme(app, "axiom_pro")

input_bar = ModernInputBar(tm)
input_bar.show()
input_bar.resize(600, 60)

pix = input_bar.grab()
pix.save("/tmp/input_bar_test.png")
print("Rendered Input Bar!")

sys.exit(0)
