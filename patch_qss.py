with open("axiom/gui/styles/base.qss.template", "r") as f:
    qss = f.read()

# Replace QLineEdit... rules
import re
new_rules = """
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background-color: @bg_surface@;
    color: @text_main@;
    border: 1px solid @borders@;
    border-radius: @radius_md@;
    padding: 8px 12px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: none;
}

QComboBox QAbstractItemView {
    background-color: @bg_surface@;
    color: @text_main@;
    border: 1px solid @borders@;
    border-radius: @radius_sm@;
    selection-background-color: @accent@;
}
"""
qss = re.sub(r'QLineEdit, QTextEdit, QPlainTextEdit, QComboBox \{.*?\n\}', new_rules.strip(), qss, flags=re.DOTALL)

with open("axiom/gui/styles/base.qss.template", "w") as f:
    f.write(qss)
