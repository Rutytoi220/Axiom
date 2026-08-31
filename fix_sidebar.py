with open('axiom/gui/main_window.py', 'r') as f:
    content = f.read()

content = content.replace('self.sidebar.layout().addWidget(self.radar_btn)', 'self.sidebar.layout.addWidget(self.radar_btn)')

with open('axiom/gui/main_window.py', 'w') as f:
    f.write(content)
