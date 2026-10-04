"""AXIOM Modern Inline Streaming CLI (REPL).

A lightweight, non-fullscreen, reactive AI streaming CLI with native terminal scrolling,
Tokyo Night / Slate aesthetics, and sub-10ms Three-Tier automation.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from rich.text import Text
from rich.theme import Theme

import axiom.agents.native_orchestrator as nat_orch
from axiom.agents.native_orchestrator import NativeOrchestrator
from axiom.config import get_config
from axiom.core.plugins import get_tool_schemas, load_plugins
from axiom.db.memory import add_message, create_session, get_session_messages

# ---------------------------------------------------------------------------
# Tokyo Night / Slate Theme Palette (High Contrast)
# ---------------------------------------------------------------------------
# Prompt glyph:         #7aa2f7 (Soft Blue)
# Labels / Subtitles:   #a9b1d6 (Crisp Readable Slate)
# Values / Active:      #7dcfff (Vibrant Cyan)
# Session:              #bb9af7 (Soft Lavender)
# Tool execution badge: #e0af68 (Warm Amber)
# Tool outputs/Success: #9ece6a (Subtle Emerald)
# User input:           #c0caf5 (Crisp Foreground)
# Error:                #f7768e (Soft Red)

TOKYO_NIGHT_THEME = Theme({
    "prompt.glyph": "#7aa2f7 bold",
    "prompt.prefix": "#a9b1d6",
    "user.input": "#c0caf5",
    "reasoning": "#a9b1d6 italic",
    "tool.badge": "#e0af68 bold",
    "tool.name": "#e0af68",
    "tool.output": "#9ece6a",
    "success": "#9ece6a bold",
    "error": "#f7768e bold",
    "dim": "#a9b1d6",
    "label": "#a9b1d6",
    "value": "#7dcfff bold",
    "session": "#bb9af7",
    "title": "#7aa2f7 bold",
    "accent": "#bb9af7",
})

console = Console(theme=TOKYO_NIGHT_THEME, highlight=False)

PROMPT_STYLE = Style.from_dict({
    "prompt-glyph": "#7aa2f7 bold",
    "prompt-prefix": "#a9b1d6",
    "": "#c0caf5",
})

BANNER = (
    r"[#7aa2f7 bold]"
    r"""
     _   __  _____ ___  __  __ 
    / \  \ \/ /_ _/ _ \|  \/  |
   / _ \  \  / | | | | | |\/| |
  / ___ \ /  \ | | |_| | |  | |
 /_/   \_\_/\_\___\___/|_|  |_|
"""
    r"[/#7aa2f7 bold]"
    "\n[#a9b1d6]Local-First AI Orchestrator  ·  Three-Tier Semantic Automation  ·  Tokyo Night[/#a9b1d6]\n"
)


def clear_screen() -> None:
    """Clear terminal viewport using standard ANSI escape codes."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


class InlineRepl:
    """Manages the interactive inline terminal REPL session."""

    def __init__(self, session_id: Optional[str] = None):
        self.config = get_config()
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"
        self.history_dir = Path.home() / ".config" / "axiom"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.history_dir / "repl_history"

        create_session(self.session_id, title="CLI Session")
        self.orchestrator = NativeOrchestrator()
        load_plugins()

        self.prompt_session: PromptSession = PromptSession(
            history=FileHistory(str(self.history_file)),
            style=PROMPT_STYLE,
        )
        self.is_running = True

    def print_banner(self) -> None:
        console.print(BANNER)
        console.print(
            f"[label]Model:[/label] [value]{self.config.ollama_model}[/value]  ·  "
            f"[label]Session:[/label] [session]{self.session_id[:8]}[/session]  ·  "
            f"[label]Type[/label] [#e0af68]/help[/#e0af68] [label]for commands or[/label] [#e0af68]/exit[/#e0af68] [label]to quit.[/label]\n"
        )

    def print_help(self) -> None:
        console.print("\n[title]Available Commands:[/title]")
        console.print("  [#e0af68]/help[/]             [label]Show this command reference[/label]")
        console.print("  [#e0af68]/clear[/]            [label]Clear the terminal screen[/label]")
        console.print("  [#e0af68]/session <name>[/]   [label]Switch or create conversation session[/label]")
        console.print("  [#e0af68]/resume[/]           [label]Display history of active session[/label]")
        console.print("  [#e0af68]/model[/]            [label]List and select active Ollama model[/label]")
        console.print("  [#e0af68]/tools[/]            [label]List active Three-Tier tools in registry[/label]")
        console.print("  [#e0af68]/exit[/], [#e0af68]/quit[/]      [label]Exit AXIOM REPL[/label]\n")

    def handle_command(self, cmd_text: str) -> bool:
        """Handles slash commands. Returns True if handled, False otherwise."""
        parts = cmd_text.strip().split()
        if not parts:
            return False

        cmd = parts[0].lower()
        if cmd in ("/exit", "/quit"):
            self.is_running = False
            console.print("[dim]Goodbye.[/dim]")
            return True

        elif cmd == "/clear":
            clear_screen()
            self.print_banner()
            return True

        elif cmd == "/help":
            self.print_help()
            return True

        elif cmd == "/session":
            if len(parts) > 1:
                self.session_id = " ".join(parts[1:])
                create_session(self.session_id, title=self.session_id)
                console.print(f"[success]✓ Switched to session '{self.session_id}'.[/success]\n")
            else:
                console.print(f"[dim]Current session ID: [/][#9ece6a]{self.session_id}[/]\n")
            return True

        elif cmd == "/resume":
            messages = get_session_messages(self.session_id)
            if not messages:
                console.print(f"[dim]No message history found for session '{self.session_id}'.[/dim]\n")
                return True

            console.print(f"\n[title]Resumed session {self.session_id[:8]} ({len(messages)} messages):[/title]")
            for m in messages:
                role = m.get("role")
                content = m.get("content", "")
                if role == "user":
                    console.print(f"\n[prompt.glyph]❯[/] [user.input]{content}[/]")
                elif role == "assistant":
                    console.print(f"\n[#7aa2f7]◈ Axiom:[/]\n{content}")
            console.print()
            return True

        elif cmd == "/model":
            import httpx
            try:
                with httpx.Client(timeout=3.0) as client:
                    resp = client.get(f"{self.config.ollama_base_url}/api/tags")
                    if resp.status_code == 200:
                        models = [m["name"] for m in resp.json().get("models", [])]
                        console.print(f"\n[title]Available Models on {self.config.ollama_base_url}:[/title]")
                        for m in models:
                            active = " [success](active)[/success]" if m == self.config.ollama_model else ""
                            console.print(f"  · [#c0caf5]{m}[/]{active}")
                        console.print()
                        return True
            except Exception as e:
                console.print(f"[error]Could not connect to Ollama: {e}[/error]\n")
                return True

        elif cmd == "/tools":
            schemas = get_tool_schemas(0)
            console.print(f"\n[title]Registered Dynamic Tools ({len(schemas)}):[/title]")
            for s in schemas:
                fn = s.get("function", {})
                name = fn.get("name", "")
                desc = fn.get("description", "")
                console.print(f"  [tool.badge]•[/tool.badge] [tool.name]{name}[/tool.name]: [dim]{desc}[/dim]")
            console.print()
            return True

        return False

    async def stream_response(self, user_prompt: str) -> None:
        """Streams LLM tokens and reasoning blocks directly to stdout."""
        # 1. Commit user message to DB
        add_message(self.session_id, "user", user_prompt)

        # 2. Build payload with dynamic tools
        dynamic_tools = get_tool_schemas(0)
        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": user_prompt}
        ]

        payload = {
            "stream": True,
            "tools": dynamic_tools,
            "messages": messages,
            "session_id": self.session_id,
        }

        # 3. Intercept execute_tool to render transient spinners during tool dispatch
        original_execute = nat_orch.execute_tool

        async def inline_execute_tool(name: str, **kwargs):
            hint = f"Executing {name}..."
            console.print(f"\n  [tool.badge]⚡ Tool Dispatch:[/tool.badge] [tool.name]{name}[/tool.name] [dim]{json.dumps(kwargs)}[/dim]")
            with console.status(f"  [#e0af68]{hint}[/#e0af68]", spinner="dots"):
                res = await original_execute(name, **kwargs)

            # Summarize result cleanly
            res_str = str(res)
            short_res = res_str[:160] + "..." if len(res_str) > 160 else res_str
            console.print(f"  [tool.output]✓ {name} completed:[/tool.output] [dim]{short_res}[/dim]\n")
            return res

        nat_orch.execute_tool = inline_execute_tool

        # 4. Stream tokens
        in_think = False
        full_content: List[str] = []
        tool_calls_emitted: List[Dict[str, Any]] = []

        console.print("\n[#7aa2f7]◈ Axiom:[/#7aa2f7] ", end="")
        sys.stdout.flush()

        try:
            async for chunk in self.orchestrator.generate_stream(payload):
                choices = chunk.get("choices", [])
                if not choices:
                    continue

                delta = choices[0].get("delta", {})

                # Tool calls capture
                if "tool_calls" in delta:
                    for tc in delta["tool_calls"]:
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            tool_calls_emitted.append(fn)

                # Reasoning delta capture
                reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                if reasoning:
                    if not in_think:
                        sys.stdout.write("\n\n  \033[38;2;169;177;214m\033[3m[Thinking] ")
                        in_think = True
                    sys.stdout.write(reasoning)
                    sys.stdout.flush()

                content = delta.get("content", "")
                if content:
                    # Check if transitioning out of <think> tag
                    if "<think>" in content:
                        parts = content.split("<think>")
                        if parts[0]:
                            sys.stdout.write(f"\033[38;2;192;202;245m{parts[0]}")
                        sys.stdout.write("\n\n  \033[38;2;169;177;214m\033[3m[Thinking] ")
                        in_think = True
                        if len(parts) > 1 and parts[1]:
                            sys.stdout.write(parts[1])
                        sys.stdout.flush()
                        continue

                    if "</think>" in content:
                        parts = content.split("</think>")
                        if in_think and parts[0]:
                            sys.stdout.write(parts[0])
                        sys.stdout.write("\033[0m\n\n\033[38;2;192;202;245m")
                        in_think = False
                        if len(parts) > 1 and parts[1]:
                            sys.stdout.write(parts[1])
                            full_content.append(parts[1])
                        sys.stdout.flush()
                        continue

                    if in_think:
                        sys.stdout.write(content)
                    else:
                        sys.stdout.write(f"\033[38;2;192;202;245m{content}")
                        full_content.append(content)
                    sys.stdout.flush()

        except Exception as e:
            console.print(f"\n[error]Streaming error: {e}[/error]")
        finally:
            # Reset formatting
            sys.stdout.write("\033[0m\n\n")
            sys.stdout.flush()
            nat_orch.execute_tool = original_execute

        # 5. Persist assistant output to DB
        final_text = "".join(full_content).strip()
        if final_text:
            add_message(self.session_id, "assistant", final_text)

    async def run_loop(self) -> None:
        """Main non-blocking interactive loop."""
        clear_screen()
        self.print_banner()

        while self.is_running:
            try:
                # Prompt with Soft Blue glyph #7aa2f7
                prompt_text = FormattedText([
                    ("class:prompt-glyph", "❯ "),
                ])
                user_input = await asyncio.to_thread(self.prompt_session.prompt, prompt_text)
                user_input = user_input.strip()

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    if self.handle_command(user_input):
                        continue

                await self.stream_response(user_input)

            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Session closed.[/dim]")
                break
            except Exception as e:
                console.print(f"[error]Error: {e}[/error]")


def run_repl(session_id: Optional[str] = None) -> None:
    """Synchronous entry point for the inline REPL."""
    repl = InlineRepl(session_id=session_id)
    asyncio.run(repl.run_loop())


if __name__ == "__main__":
    run_repl()
