import re
with open("/home/rutytoi/.gemini/antigravity/brain/4b1a1865-12cd-4748-954c-09bf630af1cf/task.md", "r") as f:
    text = f.read()

text = text.replace("- [x] PySide6-WebEngine is already installed.\n- [x] PySide6-WebEngine is already installed.", "- [x] PySide6-WebEngine is already installed.")
with open("/home/rutytoi/.gemini/antigravity/brain/4b1a1865-12cd-4748-954c-09bf630af1cf/task.md", "w") as f:
    f.write(text)
