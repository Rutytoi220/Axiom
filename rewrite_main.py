import sys

with open("main.py", "w") as f:
    f.write('''"""Top-level entrypoint preserved for backward compatibility.

Supports both CLI and GUI modes.
"""

import argparse
import sys
import os
import traceback
from pathlib import Path


def _ensure_directories():
    """Sanity check startup paths."""
    config_dir = Path.home() / ".config" / "axiom"
    data_dir = Path.home() / ".local" / "share" / "axiom"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="AXIOM - Local AI Assistant")
    parser.add_argument("--model", default=None, help="Ollama model name (optional)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show raw LLM output (debug)")
    parser.add_argument("--system-prompt", "-s", default=None, help="Persistent system prompt to prepend to each query")
    parser.add_argument("--gui", action="store_true", help="Launch GUI instead of CLI (default: CLI)")
    args = parser.parse_args()
    
    _ensure_directories()
    
    if args.gui:
        try:
            # We use the new PySide6 GUI if available
            from axiom.gui.app import run_gui
            run_gui()
        except ImportError as e:
            print(f"Error: AXIOM PySide6 GUI dependencies not available. {e}", file=sys.stderr)
            try:
                # Fallback to older Tkinter GUI
                from ui.gui import run_gui
                run_gui(model=args.model, verbose=args.verbose, system_prompt=args.system_prompt)
            except ImportError:
                print("Run 'pip install PySide6' or use CLI mode.", file=sys.stderr)
    else:
        # We might have axiom.cli or ui.cli
        try:
            from axiom.api.cli import run_repl
            run_repl()
        except ImportError:
            from ui.cli import run_repl
            run_repl(model=args.model, verbose=args.verbose, system_prompt=args.system_prompt)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        crash_log = Path.home() / ".local" / "share" / "axiom" / "axiom_crash.log"
        # Make sure directory exists even if it failed before _ensure_directories
        crash_log.parent.mkdir(parents=True, exist_ok=True)
        
        trace = traceback.format_exc()
        print(f"\\n[AXIOM FATAL CRASH]\\n{trace}", file=sys.stderr)
        
        with open(crash_log, "w") as log_file:
            log_file.write(f"AXIOM CRASH REPORT\\n")
            log_file.write(f"==================\\n")
            log_file.write(trace)
            
        sys.exit(1)
''')
