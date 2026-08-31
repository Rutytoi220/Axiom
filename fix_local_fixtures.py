import re
import glob

for filepath in glob.glob('tests/**/*.py', recursive=True):
    with open(filepath, 'r') as f:
        content = f.read()

    # Remove def qapp() fixtures from individual files
    new_content = re.sub(r'@pytest\.fixture.*?def qapp\([^)]*\):.*?(?=^@|^def |^class |\Z)', '', content, flags=re.DOTALL | re.MULTILINE)
    
    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
