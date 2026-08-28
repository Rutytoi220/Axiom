import re

with open('axiom/gui/styles/base.qss.template', 'r') as f:
    content = f.read()

# Replace QLineEdit padding
content = re.sub(r'QLineEdit, QTextEdit, QPlainTextEdit \{\n    background-color: @bg_surface@;\n    color: @text_primary@;\n    border: 1px solid @border_default@;\n    border-radius: @radius_md@;\n    padding: @spacing_sm@ @spacing_md@;', 'QLineEdit, QTextEdit, QPlainTextEdit {\n    background-color: @bg_base@;\n    color: @text_primary@;\n    border: 1px solid @border_strong@;\n    border-radius: @radius_md@;\n    padding: 8px 12px;', content)

# Replace QComboBox padding
content = re.sub(r'QComboBox \{\n    background-color: @bg_surface@;\n    color: @text_primary@;\n    border: 1px solid @border_default@;\n    border-radius: @radius_md@;\n    padding: 4px 8px;', 'QComboBox {\n    background-color: @bg_base@;\n    color: @text_primary@;\n    border: 1px solid @border_strong@;\n    border-radius: @radius_md@;\n    padding: 8px 12px;', content)

# Add QCheckBox styling
checkbox_style = """
/* =========================================================================
   CheckBox
   ========================================================================= */
QCheckBox {
    color: @text_primary@;
    spacing: 10px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid @border_strong@;
    background-color: @bg_base@;
}
QCheckBox::indicator:hover {
    border: 1px solid @accent@;
}
QCheckBox::indicator:checked {
    background-color: @accent@;
    border: 1px solid @accent@;
}
"""

if "QCheckBox" not in content:
    content += checkbox_style

with open('axiom/gui/styles/base.qss.template', 'w') as f:
    f.write(content)
