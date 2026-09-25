import os

print("Restoring file to clear the regex damage...")
os.system("git checkout axiom/gui/widgets/modern_chat.py")

path = 'axiom/gui/widgets/modern_chat.py'
with open(path, 'r') as f:
    data = f.read()

# We strictly target the exact start and end of the scrollbar declaration
start_str = "self.scroll_area = QScrollArea()"
end_str = "self.scroll_widget = QWidget()"

start_idx = data.find(start_str)
end_idx = data.find(end_str)

if start_idx != -1 and end_idx != -1:
    top = data[:start_idx]
    bottom = data[end_idx:]
    
    qss = """self.scroll_area = QScrollArea()
        self.scroll_area.verticalScrollBar().setSingleStep(15)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet('''
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 20px; border-radius: 3px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.4); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; border: none; background: none; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        ''')
        
        """
    
    with open(path, 'w') as f:
        f.write(top + qss + bottom)
    print("✅ Clean restore & liquid scrollbar injection successful!")
else:
    print("❌ Could not find target strings for safe replacement.")
