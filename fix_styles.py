import re
from pathlib import Path

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    orig_content = content
    
    # Generic regex to strip setStyleSheet calls that just set basic colors/borders.
    # We have to be careful with multi-line strings.
    # Let's use a non-greedy match for setStyleSheet("...") or setStyleSheet('''...''')
    
    # 1. update_dialog.py
    if "update_dialog.py" in str(filepath):
        content = re.sub(r'\.setStyleSheet\(\s*.*?color:\s*#a6e3a1;.*?\)', '.setObjectName("update_header")', content, flags=re.DOTALL)
        content = re.sub(r'\.setStyleSheet\(\s*.*?border-radius:\s*6px.*?\)', '.setObjectName("update_changelog")', content, count=1, flags=re.DOTALL)
        content = re.sub(r'\.setStyleSheet\(\s*.*?background-color:\s*#a6e3a1.*?\)', '.setObjectName("update_install")', content, flags=re.DOTALL)
        content = re.sub(r'\.setStyleSheet\(\s*.*?background-color:\s*#313244.*?\)', '.setObjectName("update_later")', content, flags=re.DOTALL)

    # 2. scheduler_dialog.py
    if "scheduler_dialog.py" in str(filepath):
        content = re.sub(r'self\.setStyleSheet\([^)]*\)', 'pass', content, flags=re.DOTALL)
        content = re.sub(r'header\.setStyleSheet\([^)]*\)', 'header.setObjectName("scheduler_task_label")', content, flags=re.DOTALL)
        content = re.sub(r'desc\.setStyleSheet\([^)]*\)', 'desc.setObjectName("scheduler_empty")', content, flags=re.DOTALL)
        content = re.sub(r'row\.setStyleSheet\([^)]*\)', 'row.setObjectName("scheduler_task_row")', content, flags=re.DOTALL)
        content = re.sub(r't_label\.setStyleSheet\([^)]*\)', 't_label.setObjectName("scheduler_task_label")', content, flags=re.DOTALL)
        content = re.sub(r'd_label\.setStyleSheet\([^)]*\)', 'd_label.setObjectName("scheduler_cron_label")', content, flags=re.DOTALL)
        content = re.sub(r'btn\.setStyleSheet\([^)]*color:\s*#11111b[^)]*\)', 'btn.setObjectName("scheduler_toggle")', content, flags=re.DOTALL)
        content = re.sub(r'btn\.setStyleSheet\([^)]*color:\s*#cdd6f4[^)]*\)', 'btn.setObjectName("scheduler_delete")', content, flags=re.DOTALL)

    # 3. hub_dialog.py
    if "hub_dialog.py" in str(filepath):
        content = re.sub(r'header_lbl\.setStyleSheet\([^)]*\)', 'header_lbl.setObjectName("hub_desc")', content, flags=re.DOTALL)
        content = re.sub(r'empty_lbl\.setStyleSheet\([^)]*\)', 'empty_lbl.setObjectName("hub_desc")', content, flags=re.DOTALL)
        content = re.sub(r'name_lbl\.setStyleSheet\([^)]*\)', 'name_lbl.setObjectName("hub_name")', content, flags=re.DOTALL)
        content = re.sub(r'cmd_lbl\.setStyleSheet\([^)]*\)', 'cmd_lbl.setObjectName("hub_desc")', content, flags=re.DOTALL)
        content = re.sub(r'status_lbl\.setStyleSheet\([^)]*\)', 'status_lbl.setObjectName("hub_tags")', content, flags=re.DOTALL)
        content = re.sub(r'self\.pin_label\.setStyleSheet\([^)]*\)', 'self.pin_label.setObjectName("sync_pin")', content, flags=re.DOTALL)

    # 4. system_hub_dialog.py
    if "system_hub_dialog.py" in str(filepath):
        content = re.sub(r'self\.setStyleSheet\([^)]*\)', 'pass', content, flags=re.DOTALL)
        content = re.sub(r'header\.setStyleSheet\([^)]*\)', 'header.setObjectName("hub_name")', content, flags=re.DOTALL)
        content = re.sub(r'profile_label\.setStyleSheet\([^)]*\)', 'profile_label.setObjectName("hub_author")', content, flags=re.DOTALL)
        content = re.sub(r'b\.setStyleSheet\([^)]*\)', 'b.setObjectName("plugin_card")', content, flags=re.DOTALL)
        content = re.sub(r'btn\.setStyleSheet\([^)]*\)', 'btn.setObjectName("plugin_toggle")', content, flags=re.DOTALL)

    # 5. sync_dialog.py
    if "sync_dialog.py" in str(filepath):
        content = re.sub(r'title\.setStyleSheet\([^)]*\)', 'title.setObjectName("sync_pin")', content, flags=re.DOTALL)

    # 6. general stripping of .setStyleSheet
    # Only if the file doesn't have custom logic that we missed.
    # We can just strip them all!
    content = re.sub(r'\.setStyleSheet\(\s*(?:f?["\']{1,3}.*?["\']{1,3})\s*\)', '', content, flags=re.DOTALL)
    
    # Wait, some setStyleSheet take variables like: .setStyleSheet(f"color: {color};")
    content = re.sub(r'\.setStyleSheet\([^)]*\)', '', content, flags=re.DOTALL)

    if orig_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath.name}")

target_dir = Path("axiom/gui")
for filepath in target_dir.rglob("*.py"):
    if filepath.is_file():
        process_file(filepath)

print("Done.")
