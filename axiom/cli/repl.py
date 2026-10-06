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
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
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
# Slash Command Registry & Autocompletion
# ---------------------------------------------------------------------------

COMMANDS = {
    "/help": "Show this command reference and usage guide",
    "/model": "Switch the active language or vision model",
    "/session": "Create or switch to a different conversation session",
    "/resume": "Reload and resume the previous session history",
    "/clear": "Clear the screen and reset the current viewport",
    "/effort": "Adjust reasoning effort tier (low -> adhd)",
    "/thought": "Display the last reasoning trace (or toggle with Ctrl+O)",
    "/tools": "List active Three-Tier tools in registry",
    "/memory": "Manage persistent semantic memories (/memory list, /memory add <fact>)",
    "/rules": "Display active global and local project instructions",
    "/exit": "Quit the AXIOM REPL cleanly",
}

slash_completer = WordCompleter(
    list(COMMANDS.keys()) + ["/memory list", "/memory add", "/thought toggle"],
    meta_dict={
        **COMMANDS,
        "/thought toggle": "Toggle reasoning visibility (Expanded <-> Collapsed)",
        "/memory list": "Display all stored semantic memories",
        "/memory add": "Store a permanent fact in semantic memory",
    },
    sentence=True,
    ignore_case=True,
)

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
    "completion-menu": "bg:#1a1b26 #c0caf5",
    "completion-menu.completion": "bg:#1a1b26 #a9b1d6",
    "completion-menu.completion.current": "bg:#283457 #7aa2f7 bold",
    "completion-menu.meta": "bg:#16161e #565f89 italic",
    "completion-menu.meta.current": "bg:#283457 #7dcfff italic",
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


def ensure_ollama_running(base_url: str = "http://127.0.0.1:11434") -> bool:
    """Checks if Ollama daemon is responsive; if not, attempts to spawn it."""
    import urllib.request
    clean_url = (base_url or "http://127.0.0.1:11434").rstrip("/")
    try:
        req = urllib.request.Request(f"{clean_url}/api/version", method="GET")
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass

    try:
        from axiom.services.ollama_monitor import OllamaHealthMonitor
        OllamaHealthMonitor.spawn_ollama_service()
        import time
        for _ in range(6):
            time.sleep(0.5)
            try:
                req = urllib.request.Request(f"{clean_url}/api/version", method="GET")
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    if resp.status == 200:
                        return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def select_model_interactive(models: List[str], active_model: str) -> Optional[str]:
    """Interactive inline model selector using Tokyo Night palette and ANSI cursor keys."""
    import select
    import termios
    import tty

    if not models or not sys.stdin.isatty():
        return models[0] if models else None

    idx = 0
    if active_model in models:
        idx = models.index(active_model)

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    num_lines = len(models)

    def render_list(current_idx: int) -> None:
        for i, m in enumerate(models):
            is_active = (m == active_model)
            if i == current_idx:
                tag = " \033[38;2;187;154;247m(active)\033[0m" if is_active else ""
                sys.stdout.write(f"  \033[38;2;122;162;247m\033[1m▶ \033[0m\033[38;2;125;207;255m\033[1m{m}\033[0m{tag}\r\n")
            else:
                tag = " \033[38;2;169;177;214m\033[2m(active)\033[0m" if is_active else ""
                sys.stdout.write(f"    \033[38;2;169;177;214m{m}\033[0m{tag}\r\n")
        sys.stdout.flush()

    try:
        tty.setraw(fd)
        sys.stdout.write("\033[?25l")  # Hide cursor
        sys.stdout.write("\r\n\033[38;2;122;162;247m\033[1mSelect Model\033[0m \033[38;2;169;177;214m(↑/↓: navigate, Enter: confirm, Esc: cancel)\033[0m\r\n")
        render_list(idx)

        while True:
            r, _, _ = select.select([sys.stdin], [], [], None)
            ch = sys.stdin.read(1)

            if ch == "\x1b":
                r2, _, _ = select.select([sys.stdin], [], [], 0.05)
                if r2:
                    c2 = sys.stdin.read(1)
                    if c2 in ("[", "O"):
                        c3 = sys.stdin.read(1)
                        if c3 == "A":  # Up
                            idx = (idx - 1) % num_lines
                        elif c3 == "B":  # Down
                            idx = (idx + 1) % num_lines
                    sys.stdout.write(f"\033[{num_lines}A\r")
                    render_list(idx)
                else:
                    return None  # Standalone Esc
            elif ch in ("\r", "\n"):
                return models[idx]
            elif ch == "\x03":  # Ctrl+C
                return None
            elif ch in ("k", "K"):
                idx = (idx - 1) % num_lines
                sys.stdout.write(f"\033[{num_lines}A\r")
                render_list(idx)
            elif ch in ("j", "J"):
                idx = (idx + 1) % num_lines
                sys.stdout.write(f"\033[{num_lines}A\r")
                render_list(idx)
    finally:
        # Erase the selection lines and restore cursor
        sys.stdout.write(f"\033[{num_lines + 2}A\r\033[J")
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


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

        self.last_thought: str = ""
        kb = KeyBindings()

        @kb.add("c-o")
        def _toggle_thinking(event):
            run_in_terminal(self.toggle_thinking)

        self.prompt_session: PromptSession = PromptSession(
            history=FileHistory(str(self.history_file)),
            style=PROMPT_STYLE,
            completer=slash_completer,
            complete_while_typing=True,
            auto_suggest=AutoSuggestFromHistory(),
            key_bindings=kb,
        )
        self.is_running = True
        ensure_ollama_running(self.config.ollama_base_url)

    def toggle_thinking(self) -> bool:
        """Toggles thinking visibility between expanded and collapsed, and saves to config."""
        self.config.show_thinking = not getattr(self.config, "show_thinking", True)
        self.config.save()
        state_label = "EXPANDED" if self.config.show_thinking else "COLLAPSED"
        console.print(f"\n[#7aa2f7]🧠 Thinking visibility set to:[/] [#7dcfff]{state_label}[/] [dim](saved to config)[/dim]")
        if self.config.show_thinking and self.last_thought:
            console.print(f"[dim italic #7982a9]▾ Last Thought Trace:\n{self.last_thought}[/]\n[dim #3b4261]───[/]\n")
        return self.config.show_thinking

    def print_banner(self) -> None:
        console.print(BANNER)
        think_mode = "Expanded" if getattr(self.config, "show_thinking", True) else "Collapsed"
        console.print(
            f"[label]Model:[/label] [value]{self.config.ollama_model}[/value]  ·  "
            f"[label]Session:[/label] [session]{self.session_id[:8]}[/session]  ·  "
            f"[label]Thinking:[/label] [value]{think_mode}[/value] [dim](Ctrl+O)[/dim]  ·  "
            f"[label]Type[/label] [#e0af68]/help[/#e0af68] [label]for commands or[/label] [#e0af68]/exit[/#e0af68] [label]to quit.[/label]\n"
        )

    def print_help(self) -> None:
        console.print("\n[title]Available Commands:[/title]")
        for cmd, desc in COMMANDS.items():
            console.print(f"  [#e0af68]{cmd:<16}[/#e0af68] [label]{desc}[/label]")
        console.print()

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

        elif cmd == "/effort":
            if len(parts) > 1:
                tier = parts[1].lower()
                setattr(self.config, "effort_tier", tier)
                self.config.save()
                console.print(f"[success]✓ Reasoning effort tier set to '{tier}'.[/success]\n")
            else:
                current = getattr(self.config, "effort_tier", "medium")
                console.print(f"[label]Current effort tier:[/label] [value]{current}[/value]. [label]Usage: /effort <low|medium|high|ultra|adhd>[/label]\n")
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
            if len(parts) > 1:
                target_model = parts[1].strip()
                self.config.ollama_model = target_model
                self.config.save()
                console.print(f"[success]✓ Switched model to: {target_model}[/success]\n")
                return True

            import httpx
            try:
                base_url = getattr(self.config, "ollama_base_url", "http://127.0.0.1:11434").rstrip("/")
                with httpx.Client(timeout=3.0) as client:
                    resp = client.get(f"{base_url}/api/tags")
                    if resp.status_code == 200:
                        models = [m["name"] for m in resp.json().get("models", [])]
                        if not models:
                            console.print("[error]No models found in Ollama.[/error]\n")
                            return True
                        selected = select_model_interactive(models, self.config.ollama_model)
                        if selected:
                            self.config.ollama_model = selected
                            self.config.save()
                            console.print(f"[success]✓ Switched model to: {selected}[/success]\n")
                        else:
                            console.print("[dim]Model selection cancelled.[/dim]\n")
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

        elif cmd == "/memory":
            subcmd = parts[1].lower().strip() if len(parts) > 1 else "list"
            if subcmd == "list":
                from axiom.memory.semantic import get_all_memories
                mems = get_all_memories()
                if not mems:
                    console.print("[dim]No persistent semantic memories stored yet.[/dim]\n")
                else:
                    console.print(f"\n[title]Stored Semantic Memories ({len(mems)}):[/title]")
                    for m in mems:
                        mem_id = m.get("id")
                        created = m.get("created_at", "")
                        content = m.get("content", "")
                        console.print(f"  [value]#{mem_id}[/value] [dim]({created})[/dim]: [#c0caf5]{content}[/]")
                    console.print()
                return True
            elif subcmd == "add":
                fact = cmd_text.strip().split("add", 1)[1].strip() if "add" in cmd_text else ""
                if not fact:
                    console.print("[error]Usage: /memory add <fact to remember>[/error]\n")
                    return True
                from axiom.memory.semantic import add_memory
                mem_id = add_memory(fact)
                console.print(f"[success]✓ Remembered permanent fact (#{mem_id}):[/success] [value]{fact}[/value]\n")
                return True
            else:
                console.print("[error]Usage: /memory [list | add <fact>][/error]\n")
                return True

        elif cmd == "/rules":
            from axiom.core.instructions import InstructionManager
            im = InstructionManager()
            console.print(f"\n[title]Active AXIOM Rules & Instructions:[/title]\n")

            global_text = im.get_global_instructions()
            proj_path = im.get_project_instructions_path()
            proj_text = im.get_project_instructions()

            console.print(f"[label]Global Instructions[/label] [dim]({im.global_path}):[/dim]")
            if global_text:
                console.print(f"[#c0caf5]{global_text}[/]\n")
            else:
                console.print("[dim](None defined)[/dim]\n")

            proj_label = f"({proj_path})" if proj_path else "(None found in workspace)"
            console.print(f"[label]Project Workspace Rules[/label] [dim]{proj_label}:[/dim]")
            if proj_text:
                console.print(f"[#c0caf5]{proj_text}[/]\n")
            else:
                console.print("[dim](None defined: create AXIOM.md or .axiomrules in workspace)[/dim]\n")
            return True

        elif cmd in ("/thought", "/think"):
            if len(parts) > 1 and parts[1].lower() in ("toggle", "t"):
                self.toggle_thinking()
                return True
            if self.last_thought:
                console.print(f"\n[dim italic #7982a9]▾ Last Thought Trace:\n{self.last_thought}[/]\n[dim #3b4261]───[/]\n")
            else:
                console.print("[dim]No thought trace stored from the last response.[/dim]\n")
            return True

        return False

    async def stream_response(self, user_prompt: str) -> None:
        """Streams LLM tokens and reasoning blocks directly to stdout."""
        # 0. Ensure local AI engine is responsive
        ensure_ollama_running(self.config.ollama_base_url)

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
            if in_think:
                end_thought()
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

        # 4. Stream tokens & manage collapsible reasoning
        show_thinking = getattr(self.config, "show_thinking", True)
        in_think = False
        think_source: Optional[str] = None
        thought_start_time: Optional[float] = None
        thought_token_count = 0
        last_thought_buffer: List[str] = []
        axiom_header_printed = False
        full_content: List[str] = []
        tool_calls_emitted: List[Dict[str, Any]] = []

        def ensure_axiom_header(for_thinking: bool = False) -> None:
            nonlocal axiom_header_printed
            if not axiom_header_printed:
                if for_thinking:
                    console.print("\n[#7aa2f7]◈ Axiom:[/#7aa2f7]")
                else:
                    console.print("\n[#7aa2f7]◈ Axiom:[/#7aa2f7] ", end="")
                    sys.stdout.flush()
                axiom_header_printed = True

        def start_thought(source: str = "tag") -> None:
            nonlocal in_think, thought_start_time, think_source
            if not in_think:
                in_think = True
                think_source = source
                if thought_start_time is None:
                    thought_start_time = time.time()
                ensure_axiom_header(for_thinking=True)
                if show_thinking:
                    console.print("[dim italic #7982a9]▾ Thinking:[/]")
                else:
                    sys.stdout.write(f"\r  \033[38;2;121;130;169m\033[3mThinking... ({thought_token_count} tokens)\033[0m")
                    sys.stdout.flush()

        def append_thought(text: str) -> None:
            nonlocal thought_token_count
            if not text:
                return
            last_thought_buffer.append(text)
            words = re.findall(r"\w+|[^\w\s]", text)
            thought_token_count += len(words) if words else (1 if text.strip() else 0)
            if show_thinking:
                sys.stdout.write(f"\033[38;2;121;130;169m\033[3m{text}\033[0m")
                sys.stdout.flush()
            else:
                sys.stdout.write(f"\r\033[K  \033[38;2;121;130;169m\033[3mThinking... ({thought_token_count} tokens)\033[0m")
                sys.stdout.flush()

        def end_thought() -> None:
            nonlocal in_think, think_source
            if in_think:
                in_think = False
                think_source = None
                elapsed = max(0.1, time.time() - (thought_start_time or time.time()))
                if show_thinking:
                    console.print("\n[dim #3b4261]───[/]\n")
                else:
                    sys.stdout.write("\r\033[K")
                    sys.stdout.flush()
                    console.print(f"[dim italic #7982a9]▾ Thought for {elapsed:.1f}s ({thought_token_count} tokens) [Ctrl+O to view][/]\n")

        def append_content(text: str) -> None:
            if not text:
                return
            if in_think:
                end_thought()
            ensure_axiom_header(for_thinking=False)
            sys.stdout.write(f"\033[38;2;192;202;245m{text}")
            sys.stdout.flush()
            full_content.append(text)

        try:
            async for chunk in self.orchestrator.generate_stream(payload):
                choices = chunk.get("choices", [])
                if not choices:
                    continue

                delta = choices[0].get("delta", {})

                # Tool calls capture
                if "tool_calls" in delta:
                    if in_think:
                        end_thought()
                    for tc in delta["tool_calls"]:
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            tool_calls_emitted.append(fn)

                # Reasoning delta capture (field-based)
                reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                if reasoning:
                    if not in_think:
                        start_thought(source="field")
                    append_thought(reasoning)
                elif in_think and think_source == "field":
                    end_thought()

                raw_content = delta.get("content", "")
                if raw_content:
                    if in_think and think_source == "field":
                        end_thought()

                    cursor = 0
                    while cursor < len(raw_content):
                        if not in_think:
                            if "<think>" in raw_content[cursor:]:
                                idx = raw_content.find("<think>", cursor)
                                before = raw_content[cursor:idx]
                                if before:
                                    append_content(before)
                                start_thought(source="tag")
                                cursor = idx + len("<think>")
                            else:
                                append_content(raw_content[cursor:])
                                break
                        else:
                            if "</think>" in raw_content[cursor:]:
                                idx = raw_content.find("</think>", cursor)
                                thought_chunk = raw_content[cursor:idx]
                                if thought_chunk:
                                    append_thought(thought_chunk)
                                end_thought()
                                cursor = idx + len("</think>")
                            else:
                                append_thought(raw_content[cursor:])
                                break

        except Exception as e:
            console.print(f"\n[error]Streaming error: {e}[/error]")
        finally:
            if in_think:
                end_thought()
            # Reset formatting
            sys.stdout.write("\033[0m\n\n")
            sys.stdout.flush()
            nat_orch.execute_tool = original_execute

        # 5. Store accumulated reasoning trace for inspection / Ctrl+O
        if last_thought_buffer:
            self.last_thought = "".join(last_thought_buffer).strip()

        # 6. Persist assistant output to DB
        final_text = "".join(full_content).strip()
        if final_text:
            add_message(self.session_id, "assistant", final_text)

    async def run_loop(self) -> None:
        """Main non-blocking interactive loop."""
        clear_screen()
        self.print_banner()

        # Eagerly spawn and start BrowserExtensionBridge server on 127.0.0.1:41144
        try:
            from axiom.tools.browser_extension import get_bridge
            bridge = get_bridge()
            asyncio.create_task(bridge.start_server())
        except Exception:
            pass

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
