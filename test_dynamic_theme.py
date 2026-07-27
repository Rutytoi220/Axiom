import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
import axiom.gui.app as gui_app
from axiom.config import get_config

app = QApplication(sys.argv)
config = get_config()
config.theme_mode = "dark"
gui_app._load_stylesheet(app)

w = QMainWindow()
w.setWindowTitle("Test")
b = QPushButton("Switch to Light")
def switch():
    config.theme_mode = "light"
    gui_app._load_stylesheet(app)
    print("Switched! New length:", len(app.styleSheet()))
b.clicked.connect(switch)

cw = QWidget()
l = QVBoxLayout(cw)
l.addWidget(b)
w.setCentralWidget(cw)
w.show()
switch()
