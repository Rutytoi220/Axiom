import re
with open('tests/gui/test_v60_automation.py', 'r') as f:
    content = f.read()

content = content.replace('async def test_all():', 'async def test_all(qapp):')

with open('tests/gui/test_v60_automation.py', 'w') as f:
    f.write(content)

with open('tests/gui/test_v58.py', 'r') as f:
    content2 = f.read()

content2 = content2.replace('def test_v58_sync():', 'def test_v58_sync(qapp):')

with open('tests/gui/test_v58.py', 'w') as f:
    f.write(content2)

with open('tests/gui/test_v57.py', 'r') as f:
    content3 = f.read()

content3 = content3.replace('def test_v57_widgets():', 'def test_v57_widgets(qapp):')

with open('tests/gui/test_v57.py', 'w') as f:
    f.write(content3)

with open('tests/gui/test_v56.py', 'r') as f:
    content4 = f.read()

content4 = content4.replace('def test_gui_v56_main():', 'def test_gui_v56_main(qapp):')

with open('tests/gui/test_v56.py', 'w') as f:
    f.write(content4)

with open('tests/gui/test_v60.py', 'r') as f:
    content5 = f.read()

content5 = content5.replace('def test_v60():', 'def test_v60(qapp):')

with open('tests/gui/test_v60.py', 'w') as f:
    f.write(content5)
    
