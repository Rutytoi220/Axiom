import re

with open('AXIOM.spec', 'r') as f:
    content = f.read()

excludes_list = "['tkinter', 'PySide6.QtWebEngine', 'PySide6.QtWebEngineCore', 'PySide6.QtQml', 'PySide6.Qt3D', 'PySide6.QtQuick', 'PySide6.QtBluetooth', 'PySide6.QtMultimedia', 'matplotlib', 'jupyter', 'IPython', 'notebook', 'scipy', 'pandas']"
content = re.sub(r"excludes=\['tkinter'\]", f"excludes={excludes_list}", content)

with open('AXIOM.spec', 'w') as f:
    f.write(content)
