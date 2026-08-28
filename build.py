import subprocess
import sys
import os

def main():
    try:
        import PyInstaller
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    args = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--name", "AXIOM",
        "--exclude-module", "tkinter",
        "--hidden-import", "PySide6",
        "--hidden-import", "cryptography",
        "--hidden-import", "aiohttp",
        "--hidden-import", "sqlite3",
        "--hidden-import", "axiom",
        "--collect-data", "litellm",
        "--collect-all", "litellm",
        "--collect-all", "tiktoken",
        "--hidden-import", "tiktoken_ext.openai_public",
        "--hidden-import", "tiktoken_ext",
        "--add-data", "axiom/gui/styles:axiom/gui/styles",
        "--add-data", "axiom/gui/assets:axiom/gui/assets",
        "--add-data", "axiom/memory/schema.sql:axiom/memory",
        "--add-data", "axiom/client/tui/monitor.tcss:axiom/client/tui",
        "axiom/launcher.py"
    ]
    
    print("Running PyInstaller...")
    subprocess.run(args, check=True)
    print("Build complete.")

if __name__ == "__main__":
    main()
