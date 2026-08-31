import re

with open('axiom/gui/widgets/update_dialog.py', 'r') as f:
    content = f.read()

prefix = """class DownloadUpdateThread(QThread):
    progress = Signal(int)
    finished_download = Signal(bool, str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url
"""

content = re.sub(r'    def __init__\(self, url: str\):\n        super\(\)\.__init__\(\)\n        self\.url = url\n', prefix, content)

with open('axiom/gui/widgets/update_dialog.py', 'w') as f:
    f.write(content)

