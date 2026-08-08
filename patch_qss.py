import sys

with open("axiom/gui/windows/oobe_window.py", "r") as f:
    text = f.read()

text = text.replace('background-color: #18181B;', 'background-color: #1e1e2e;')
text = text.replace('border: 2px solid #3F3F46;', 'border: 2px solid #313244;')
text = text.replace('border: 1px solid #3F3F46;', 'border: 1px solid #313244;')
text = text.replace('background-color: #27272A;', 'background-color: #11111b;')
text = text.replace('background-color: #3F3F46;', 'background-color: #313244;')

with open("axiom/gui/windows/oobe_window.py", "w") as f:
    f.write(text)
