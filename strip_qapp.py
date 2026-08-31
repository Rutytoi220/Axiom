import os
import re

files_to_strip = [
    'tests/unit/test_updater_reliability.py',
    'tests/gui/test_dynamic_theme.py',
    'tests/gui/test_v57.py',
    'tests/gui/test_gui_hub.py',
    'tests/gui/test_v58.py',
    'tests/gui/test_v56.py',
    'tests/gui/test_v60.py',
    'tests/gui/test_v60_automation.py',
    'tests/gui/test_telemetry_hud.py',
]

for file_path in files_to_strip:
    if not os.path.exists(file_path):
        continue
    with open(file_path, 'r') as f:
        content = f.read()

    # Remove app = QApplication(...) or app = QtWidgets.QApplication(...)
    content = re.sub(r'^\s*app\s*=\s*(?:QtWidgets\.)?QApplication\..*?$', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*app\s*=\s*(?:QtWidgets\.)?QApplication\(.*?\).*?$', '', content, flags=re.MULTILINE)

    with open(file_path, 'w') as f:
        f.write(content)

