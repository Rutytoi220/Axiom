import re

with open("axiom/gui/widgets/modern_chat.py", "r") as f:
    content = f.read()

new_input_bar = """        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(16, 0, 16, 0)
        self.layout.setSpacing(12)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        from PySide6.QtWidgets import QStyle

        self.attach_btn = QPushButton()
        self.attach_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.attach_btn.setObjectName("attach_btn")
        self.attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.attach_btn.setFixedSize(40, 40)

        self.input_area = AutoExpandTextEdit(theme_manager)
        self.input_edit = self.input_area  # ALIAS for main_window.py
        self.input_area.setFixedHeight(40)
        
        self.mic_btn = QPushButton()
        self.mic_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume))
        self.mic_btn.setCheckable(True)
        self.mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_btn.setFixedSize(40, 40)
        self.mic_btn.toggled.connect(self.mic_toggled.emit)
        
        self.send_btn = QPushButton()
        self.send_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setFixedSize(40, 40)
        self.send_btn.clicked.connect(self._on_send)
        
        self.input_area.return_pressed.connect(self.send_btn.click)

        self.layout.addWidget(self.attach_btn)
        self.layout.addWidget(self.input_area)
        self.layout.addWidget(self.mic_btn)
        self.layout.addWidget(self.send_btn)"""

old_input_bar = r'        self\.layout = QHBoxLayout\(self\).*?self\.layout\.addWidget\(self\.send_btn, 0, Qt\.AlignmentFlag\.AlignBottom\)'
content = re.sub(old_input_bar, new_input_bar, content, flags=re.DOTALL)

# Also let's modify AutoExpandTextEdit to default to 40
content = re.sub(r'self\.setFixedHeight\(24\)', 'self.setFixedHeight(40)', content)
content = re.sub(r'new_height = max\(24, min\(int\(doc_height\) \+ 4, 120\)\)', 'new_height = max(40, min(int(doc_height) + 4, 120))', content)

with open("axiom/gui/widgets/modern_chat.py", "w") as f:
    f.write(content)

