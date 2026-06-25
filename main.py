"""Top-level entrypoint preserved for backward compatibility.

Supports both CLI and GUI modes.
"""

from ui.cli import run_repl
import argparse


def main():
    parser = argparse.ArgumentParser(description="ChienGPT / AXIOM - Local AI Assistant")
    parser.add_argument("--model", default=None, help="Ollama model name (optional)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show raw LLM output (debug)")
    parser.add_argument("--system-prompt", "-s", default=None, help="Persistent system prompt to prepend to each query")
    parser.add_argument("--gui", action="store_true", help="Launch GUI instead of CLI (default: CLI)")
    args = parser.parse_args()
    
    if args.gui:
        try:
            from ui.gui import run_gui
            run_gui(model=args.model, verbose=args.verbose, system_prompt=args.system_prompt)
        except ImportError as e:
            print(f"Error: GUI dependencies not available. {e}")
            print("Run 'pip install tkinter' or use CLI mode (default)")
    else:
        run_repl(model=args.model, verbose=args.verbose, system_prompt=args.system_prompt)


if __name__ == "__main__":
    main()