import pytest
from PySide6.QtCore import Qt
from axiom.gui.widgets.hub_dialog import AxiomHubDialog

def test_hub_dialog_initialization(qtbot):
    dialog = AxiomHubDialog()
    qtbot.addWidget(dialog)
    
    assert dialog.windowTitle() == "AXIOM Hub"
    assert dialog.tabs.count() == 2

def test_hub_install_flow(qtbot, mock_home_directory, mocker):
    # Mock network fetching so it uses DEFAULT_MANIFEST instead of stalling
    mocker.patch("axiom.gui.widgets.hub_dialog.MANIFEST_URL", "http://invalid.url")
    
    dialog = AxiomHubDialog()
    qtbot.addWidget(dialog)
    
    # Wait for the manifest to finish fetching and render tools
    def check_cards():
        assert dialog.scroll_layout.count() > 0
    qtbot.waitUntil(check_cards, timeout=1000)
    
    # Get the install button from the first card
    card = dialog.scroll_layout.itemAt(0).widget()
    # It's a QHBoxLayout. The last widget is the install button.
    install_btn = card.layout().itemAt(card.layout().count() - 1).widget()
    
    assert install_btn.text() == "1-Click Install"
    
    with qtbot.waitSignal(dialog.tool_installed, timeout=2000) as blocker:
        qtbot.mouseClick(install_btn, Qt.MouseButton.LeftButton)
        
    assert blocker.args == ["sys_info"]
    assert install_btn.text() == "Installed"
