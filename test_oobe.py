import sys
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication
from axiom.gui.app import _load_stylesheet
from axiom.gui.widgets.oobe_wizard import OobeWizardDialog

app = QApplication(sys.argv)
_load_stylesheet(app)

wizard = OobeWizardDialog()
wizard.show()
wizard.resize(800, 600)

pix = wizard.grab()
pix.save("/tmp/oobe_test.png")
print("Rendered OOBE!")

# Click next through pages
wizard.nav_btn.click()
print("Clicked Next to Theme Page")

# Click first theme
wizard.theme_cards[0].clicked.emit(wizard.theme_cards[0].card_key)
print("Theme Applied Live!")

pix = wizard.grab()
pix.save("/tmp/oobe_theme_test.png")
print("Rendered OOBE Theme!")

sys.exit(0)
