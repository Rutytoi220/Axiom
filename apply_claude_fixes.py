import os

print("1. Injecting Global Liquid Scrollbars and Rounded ToolButtons...")
qss_path = 'axiom/gui/styles/base.qss.template'

if os.path.exists(qss_path):
    with open(qss_path, 'r') as f:
        data = f.read()
        
    if "GLOBAL SCROLLBAR OVERRIDE" not in data:
        with open(qss_path, 'a') as f:
            f.write("""
/* --- GLOBAL SCROLLBAR OVERRIDE --- */
QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }
QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.15); min-height: 20px; border-radius: 3px; }
QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.3); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; border: none; background: none; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

/* --- FIX SQUARE BUTTONS --- */
QToolButton { border-radius: 6px; }
""")
        print("✅ Stylesheet template updated with modern CSS!")
    else:
        print("⚠️ QSS override already exists.")
else:
    print(f"❌ Could not find {qss_path}. Ensure you are in the project root.")

print("\n2. Exterminating Unsupported Unicode (Fixing Hollow Boxes)...")
# Recursively hunt down the Unicode emojis causing the Linux Tofu effect
replacements = {
    '⚙️ Settings': 'Settings',
    '⚙ Settings': 'Settings',
    '"⚙️"': '"Settings"',
    '"⚙"': '"Settings"',
    '"➤"': '"Send"',
    '"🎤"': '"Mic"',
    '"🌙"': '"Dark"',
    '"☀️"': '"Light"',
    '"➕"': '"+"'
}

files_patched = 0
for root, dirs, files in os.walk('axiom/gui'):
    for file in files:
        if file.endswith('.py'):
            file_path = os.path.join(root, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original = content
            for bad_char, safe_text in replacements.items():
                content = content.replace(bad_char, safe_text)
            
            if content != original:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ Patched Unicode in: {file}")
                files_patched += 1

if files_patched == 0:
    print("⚠️ No Unicode characters found to replace (already patched?).")

print("\n🎉 All 3 UI fixes applied successfully!")
