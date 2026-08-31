with open('tests/gui/test_gui_hub.py', 'r') as f:
    content = f.read()

bad_asserts = """    assert dialog.tabs.count() == 3
    assert dialog.tabs.tabText(2) == "🔌 MCP Servers"
"""
good_asserts = """    assert dialog.tabs.count() == 4
    assert dialog.tabs.tabText(0) == "Tools"
    assert dialog.tabs.tabText(1) == "Themes"
    assert dialog.tabs.tabText(2) == "🔌 MCP Servers"
    assert dialog.tabs.tabText(3) == "💻 Swarm Sync"
"""
content = content.replace(bad_asserts, good_asserts)

with open('tests/gui/test_gui_hub.py', 'w') as f:
    f.write(content)
