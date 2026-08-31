with open('tests/gui/test_oobe_window.py', 'r') as f:
    content = f.read()

bad_block = """        oobe_window._on_finish()"""
good_block = """        with qtbot.waitSignal(oobe_window.initialization_complete, timeout=3000):
            oobe_window._on_finish()"""

content = content.replace(bad_block, good_block)

with open('tests/gui/test_oobe_window.py', 'w') as f:
    f.write(content)
