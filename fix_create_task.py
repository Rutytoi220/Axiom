import os
import re

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    if 'asyncio.create_task' not in content:
        return

    # Let's just create a helper and replace asyncio.create_task with axiom_create_task?
    # Better: append a .add_done_callback if it's a simple call
    pass

