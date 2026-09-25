import re

with open("axiom/gui/styles/base.qss.template", "r") as f:
    content = f.read()

# 1. QPushButton, QToolButton
content = re.sub(
    r'QPushButton, QToolButton \{\s*background-color: @bg_surface@;\s*color: @text_main@;\s*border: 1px solid @borders@;\s*border-radius: @radius_md@;',
    'QPushButton, QToolButton {\n    background-color: @bg_surface@;\n    color: @text_main@;\n    border: 1px solid @borders@;\n    border-radius: @radius_pill@;',
    content
)

# 2. Text Input Box
content = re.sub(
    r'QLineEdit, QTextEdit, QPlainTextEdit, QComboBox \{\s*background-color: @bg_surface@;\s*color: @text_main@;\s*border: 1px solid @borders@;\s*border-radius: @radius_md@;',
    'QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {\n    background-color: @bg_surface@;\n    color: @text_main@;\n    border: 1px solid @borders@;\n    border-radius: @radius_pill@;',
    content
)

# 3. Message Bubbles
content = re.sub(
    r'QFrame#chat_bubble \{\s*border-radius: @radius_lg@;',
    'QFrame#chat_bubble {\n    border-radius: @radius_pill@;',
    content
)

# 4. Segmented Control
content = re.sub(
    r'QFrame#segmented_control \{\s*background-color: @bg_surface@;\s*border-radius: @radius_md@;',
    'QFrame#segmented_control {\n    background-color: @bg_surface@;\n    border-radius: @radius_pill@;',
    content
)
content = re.sub(
    r'QPushButton#segmented_btn\[position="first"\] \{\s*border-top-left-radius: @radius_md@;\s*border-bottom-left-radius: @radius_md@;',
    'QPushButton#segmented_btn[position="first"] {\n    border-top-left-radius: @radius_pill@;\n    border-bottom-left-radius: @radius_pill@;',
    content
)
content = re.sub(
    r'QPushButton#segmented_btn\[position="last"\] \{\s*border-top-right-radius: @radius_md@;\s*border-bottom-right-radius: @radius_md@;',
    'QPushButton#segmented_btn[position="last"] {\n    border-top-right-radius: @radius_pill@;\n    border-bottom-right-radius: @radius_pill@;',
    content
)

# 5. Circle Buttons
old_attach = r'QPushButton#attach_btn \{\s*background: transparent;\s*color: @text_muted@;\s*font-size: 24px;\s*font-weight: bold;\s*border: none;\s*padding-bottom: 2px;\s*\}'
old_attach_hover = r'QPushButton#attach_btn:hover \{\s*color: @text_main@;\s*\}'

new_circle_btns = """QPushButton#attach_btn, QPushButton#mic_btn, QPushButton#send_btn {
    background-color: @bg_surface@;
    border: 1px solid @borders@;
    border-radius: @radius_circle@;
    padding: 0px;
}
QPushButton#attach_btn:hover, QPushButton#mic_btn:hover, QPushButton#send_btn:hover {
    background-color: @primary@;
    border: 1px solid @primary@;
}"""

content = re.sub(old_attach, new_circle_btns, content)
content = re.sub(old_attach_hover, '', content)

with open("axiom/gui/styles/base.qss.template", "w") as f:
    f.write(content)

print("Geometry Patched.")
