import os
import re

path = 'axiom/gui/widgets/modern_chat.py'
if os.path.exists(path):
    with open(path, 'r') as f:
        data = f.read()

    # 1. Strip out any broken setStyleSheet calls applied to the scroll_area
    data = re.sub(r'self\.scroll_area\.setStyleSheet\([^)]+\)', '', data)

    # 2. Inject the flawless liquid scrollbar QSS (using standard strings, NOT f-strings)
    target = 'self.scroll_area = QScrollArea()'
    if target in data and 'setSingleStep(15)' not in data:
        qss = """self.scroll_area = QScrollArea()
        self.scroll_area.verticalScrollBar().setSingleStep(15)
        self.scroll_area.setStyleSheet('''
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 20px; border-radius: 3px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.4); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; border: none; background: none; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        ''')"""
        data = data.replace(target, qss)
        
        with open(path, 'w') as f:
            f.write(data)
        print("✅ Liquid scrollbar injected!")
    else:
        print("⚠️ Scrollbar target not found or already patched.")
