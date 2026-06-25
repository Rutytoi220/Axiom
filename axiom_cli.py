#!/usr/bin/env python3
"""AXIOM - AI Orchestration Framework entry point."""

import sys
import json
import logging
import argparse
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_task(task: str, use_tools: bool = True, session_id: Optional[str] = None, verbose: bool = False) -> dict:
    """Initialize AXIOM and run a single task, returning result dict."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    from axiom.api.cli import CLI
    cli = CLI()
    
    # If session_id provided, load or switch
    if session_id:
        cli.memory.set_conversation(session_id)
        # Pull history from memory manager into orchestrator history
        history = cli.memory.get_conversation_history()
        for msg in history:
            # Reconstruct history for orchestrator (basic roles)
            if msg["role"] in ["user", "assistant", "system", "tool"]:
                cli.orchestrator._chat_history.append({"role": msg["role"], "content": msg["content"]})
    
    # Add orchestrator message capture logic to save to memory manager
    def _memory_capture(event_name, payload):
        if event_name == "orchestrator.task.received":
            cli.memory.add_message("user", payload.get("task", ""))
        elif event_name == "orchestrator.task.completed":
            cli.memory.add_message("assistant", "Task completed.")

    cli.orchestrator.bus = type('BusMock', (), {'publish': _memory_capture})()

    result = cli.orchestrator.run(task, use_tools=use_tools, session_id=session_id)

    # Save final structured result to memory
    if result.success and isinstance(result.output, dict):
        response = result.output.get("response", "")
        cli.memory.add_message("assistant", response)

    return {
        "success": result.success,
        "output": result.output,
        "error": result.error,
        "steps": result.steps_taken,
        "metadata": result.metadata,
    }


def main():
    parser = argparse.ArgumentParser(description="AXIOM - Local AI Autonomous Agent")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run a one-shot task")
    run_parser.add_argument("task", nargs="+", help="The task for the agent to execute")
    run_parser.add_argument("--no-tools", action="store_true", help="Run without providing any tools to the LLM")
    run_parser.add_argument("--verbose", action="store_true", help="Print verbose step-by-step logs")
    run_parser.add_argument("--session-id", type=str, help="Resume an existing memory session ID")

    # Interactive command
    subparsers.add_parser("interactive", help="Start the interactive REPL mode")
    
    args = parser.parse_args()

    if args.command == "run":
        task_str = " ".join(args.task)
        try:
            result = run_task(
                task=task_str, 
                use_tools=not args.no_tools, 
                session_id=args.session_id, 
                verbose=args.verbose
            )
            print(json.dumps(result, indent=2, default=str))
            sys.exit(0 if result.get("success") else 1)
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            print(json.dumps({"success": False, "error": str(e)}, indent=2))
            sys.exit(1)
            
    elif args.command == "interactive" or not args.command:
        # Interactive REPL mode
        from axiom.main import main as repl_main
        try:
            repl_main()
        except KeyboardInterrupt:
            print("\n\nShutdown requested by user")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)

if __name__ == "__main__":
    main()
