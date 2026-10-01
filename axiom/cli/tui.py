"""AXIOM Opencode-tier Full-Screen TUI Engine.

A continuous, full-screen interactive terminal interface built natively on
``prompt_toolkit`` using a root ``FloatContainer``, ``HSplit`` layout,
and asynchronous non-blocking event loops.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import HTML, FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import (
    ConditionalContainer,
    Float,
    FloatContainer,
    HSplit,
    Window,
)
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.completion import Completer, Completion
from axiom.config import get_config
import httpx

# ---------------------------------------------------------------------------

class CognitiveLexer(Lexer):
    def lex_document(self, document):
        lines = document.lines
        line_styles = []
        in_thought = False
        
        for line in lines:
            fragments = []
            rest = line
            while True:
                if "🚨 **[Homelab Alert]**" in rest or "🚨 [Homelab Alert]" in rest or "Homelab Alert" in rest:
                    fragments.append(("class:critical-alert", rest))
                    break
                if rest.startswith("[Webhook:") or rest.startswith("[Watcher:"):
                    fragments.append(("class:cron-alert", rest))
                    break
                if "[⚙️" in rest:
                    fragments.append(("class:pipeline-step", rest))
                    break
                if rest.startswith("[Cron]"):
                    fragments.append(("class:cron-alert", rest))
                    break
                if rest.startswith("[Pipeline]") or "[System]" in rest or "[Daemon" in rest:
                    fragments.append(("class:pipeline-step", rest))
                    break
                if in_thought:
                    idx = rest.find("\u200c")
                    if idx != -1:
                        fragments.append(("class:reasoning", rest[:idx+1]))
                        rest = rest[idx+1:]
                        in_thought = False
                    else:
                        fragments.append(("class:reasoning", rest))
                        break
                else:
                    idx = rest.find("\u200b")
                    if idx != -1:
                        fragments.append(("class:content", rest[:idx+1]))
                        rest = rest[idx+1:]
                        in_thought = True
                    else:
                        fragments.append(("class:content", rest))
                        break
            line_styles.append(fragments)
            
        def get_line(lineno):
            return line_styles[lineno] if lineno < len(line_styles) else [("", "")]
        return get_line

# Constants & Global State
# ---------------------------------------------------------------------------

VERSION = "v11.2"
MODEL_LABEL = "Core · MiMo-V2.6 (local) · Bazzite-Wayland"
CURRENT_EFFORT = "medium"
CURRENT_COGNITIVE_MODE = "Standard"

execution_trace: list[Any] = []
last_ai_response = ""
current_tool_status = ""
MODAL_VISIBLE: bool = False
active_modal: str | None = None
effort_index: int = 1
model_list: list[str] = []
filtered_model_list: list[str] = []
model_index: int = 0

CURRENT_SESSION_ID: str = ""

from axiom.core.plugins import get_tui_hints
TOOL_STATE_MAP = get_tui_hints()
if not TOOL_STATE_MAP:
    TOOL_STATE_MAP = {"default": "Working..."}

COMMAND_REGISTRY: dict[str, str] = {
    "/help": "Show this help message.",
    "/clear": "Clear the chat history.",
    "/new": "Start a new conversation session.",
    "/quit": "Exit AXIOM TUI.",
    "/exit": "Exit AXIOM TUI.",
    "/cwd": "Print the current working directory.",
    "/ver": "Print the AXIOM version.",
    "/copy": "Copy the last AI response to the clipboard.",
    "/effort": "Open effort modal or set effort tier (Usage: /effort <tier>)",
    "/model": "Open model selection modal",
    "/mode": "Cycle cognitive mode.",
}

AGENT_REGISTRY: dict[str, str] = {
    "MiMo-V2.6": "Local vision & system automation (Active)",
    "Orchestrator": "Task planner & delegator",
    "Qwen-Coder": "Code generation & review",
}

from axiom.core.config import get_model_routing, get_cognitive_modes

_models = get_model_routing()
_cog_modes = get_cognitive_modes()

EFFORT_TIERS = []
for m_id in ["low", "medium", "balanced", "high", "max", "ultra"]:
    if m_id in _models:
        label = "ULTRA" if m_id == "ultra" else m_id
        EFFORT_TIERS.append({"id": m_id, "label": label, "category": "compute", "desc": f"Compute tier mapped to {_models[m_id]}"})

for c_id, c_data in _cog_modes.items():
    EFFORT_TIERS.append({"id": c_id, "label": c_id, "category": "cognitive", "desc": "Custom cognitive override active."})


def render_effort_modal_content() -> FormattedText:
    """Render the Claude Code-style interactive effort & cognitive slider."""
    tier = EFFORT_TIERS[effort_index]
    is_ultra = tier["id"] == "ultra"
    t_val = time.time()

    width = 80
    height = 9
    xc = width / 2
    yc = height / 2

    canvas_chars = [[" " for _ in range(width)] for _ in range(height)]

    def put_string(y: int, x: int, s: str) -> None:
        for i, c in enumerate(s):
            if x + i < width:
                canvas_chars[y][x + i] = c

    put_string(0, 2, "Faster")
    put_string(0, 39, "Smarter")

    labels = [t["label"] for t in EFFORT_TIERS]
    positions = [2, 10, 21, 30, 39, 50, 67]

    for x in range(width):
        canvas_chars[3][x] = "─"

    canvas_chars[3][47] = "┊"

    for i, p in enumerate(positions):
        label = labels[i]
        put_string(2, p, label)
        canvas_chars[3][p + len(label) // 2] = "┼"
        if i == effort_index:
            canvas_chars[4][p + len(label) // 2] = "▲"

    put_string(6, 2, tier["desc"])
    put_string(8, 2, "←/→ to adjust · Enter to confirm · Esc to cancel")

    fragments = []
    for y in range(height):
        for x in range(width):
            c = canvas_chars[y][x]

            if is_ultra:
                dist = math.sqrt((2 * (x - xc)) ** 2 + (y - yc) ** 2)
                intensity = math.sin(dist * 0.6 - t_val * 5.0)
                if intensity < -0.5:
                    bg = "bg:#1a0033"
                elif intensity < 0:
                    bg = "bg:#4b0082"
                elif intensity < 0.5:
                    bg = "bg:#9932cc"
                else:
                    bg = "bg:#d8b4fe"
            else:
                bg = ""

            fg = "fg:#ffffff"
            for i, p in enumerate(positions):
                label = labels[i]
                if y == 2 and p <= x < p + len(label):
                    if i == effort_index:
                        if label == "ULTRA":
                            fg = "fg:#ff55ff bold"
                        elif i > 4:
                            fg = "fg:#ffff00 bold"
                        else:
                            fg = "fg:#00ffff bold"
                    else:
                        fg = "fg:#666666"

            if y == 3:
                fg = "fg:#888888" if not is_ultra else "fg:#ff77ff bold"
            if y == 4 and c == "▲":
                fg = "fg:#ffffff bold"
            if y == 8:
                fg = "fg:#888888"

            style = f"{fg} {bg}".strip()
            fragments.append((style, c))
        if y < height - 1:
            fragments.append(("", "\n"))

    return FormattedText(fragments)



class SlashCommandCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        word = text.split()[-1] if text.split() else text
        if word.startswith('/'):
            for cmd, desc in COMMAND_REGISTRY.items():
                if cmd.startswith(word):
                    yield Completion(
                        cmd,
                        start_position=-len(word),
                        display=cmd,
                        display_meta=desc
                    )


def render_model_modal_content() -> FormattedText:
    lines = []
    lines.append(("class:modal-text", "  Available Models:\n"))
    
    visible_count = 7
    if not filtered_model_list:
        lines.append(("class:reasoning", "    No models found.\n"))
        for _ in range(visible_count - 1): lines.append(("", "\n"))
    else:
        start_idx = max(0, min(model_index - visible_count // 2, len(filtered_model_list) - visible_count))
        end_idx = min(len(filtered_model_list), start_idx + visible_count)
        
        for i in range(start_idx, end_idx):
            prefix = "  ▶ " if i == model_index else "    "
            style = "class:input-field" if i == model_index else "class:modal-text"
            lines.append((style, f"{prefix}{filtered_model_list[i]}\n"))
            
        for _ in range(visible_count - (end_idx - start_idx)):
            lines.append(("", "\n"))
            
    lines.append(("class:modal-text", "\n  Effort Tier:\n  "))
    
    slider_str = ""
    for i, t in enumerate(EFFORT_TIERS):
        if i == effort_index:
            slider_str += f"[{t['label']}]"
        else:
            slider_str += f" {t['label']} "
        if i < len(EFFORT_TIERS) - 1:
            slider_str += "---"
            
    lines.append(("class:system-alert", slider_str + "\n\n"))
    lines.append(("class:reasoning", "  ↑/↓: Model · ←/→: Effort Tier · Enter: Confirm · Esc: Cancel\n"))
    
    return FormattedText(lines)

def get_modal_title() -> str:
    """Return the title for the active modal."""
    if active_modal == "model":
        return "Model & Effort Selection"
    if active_modal == "effort":
        return "Effort & Cognitive Mode"
    if active_modal == "agents":
        return "Agents"
    if active_modal == "commands":
        return "Commands"
    if active_modal == "trace":
        return "AXIOM Debug Trace"
    return "Dialog"


def get_modal_content() -> Any:
    """Return the content for the active modal."""
    if active_modal == "model":
        return render_model_modal_content()
    elif active_modal == "effort":
        return render_effort_modal_content()
    elif active_modal == "agents":
        lines = ["\n ⬡ Available Agents:\n\n"]
        for agent, desc in AGENT_REGISTRY.items():
            lines.append(f"  • {agent:<14} - {desc}\n")
        lines.append("\n  [Press Esc or Tab to close]")
        return FormattedText([("class:modal-text", "".join(lines))])
    elif active_modal == "commands":
        lines = ["\n ⬡ Available Commands:\n\n"]
        for cmd, desc in COMMAND_REGISTRY.items():
            lines.append(f"  {cmd:<10} - {desc}\n")
        lines.append("\n  [Press Esc or Ctrl+P to close]")
        return FormattedText([("class:modal-text", "".join(lines))])
    elif active_modal == "trace":
        trace_str = json.dumps(execution_trace, indent=2) if execution_trace else "No tools executed yet."
        return FormattedText([
            ("class:modal-text", f"\n ⬡ AXIOM Debug Trace:\n\n{trace_str}\n\n  [Press Esc or Ctrl+O to close]")
        ])
    return FormattedText([("", "")])


# ---------------------------------------------------------------------------
# UI Construction & Application Engine
# ---------------------------------------------------------------------------

def create_tui_app() -> Application[None]:
    """Construct and return the full-screen prompt_toolkit Application."""
    global effort_index

    # Initialize effort_index from CURRENT_EFFORT / CURRENT_COGNITIVE_MODE
    for i, t in enumerate(EFFORT_TIERS):
        if t["category"] == "compute" and t["label"].lower() == CURRENT_EFFORT.lower():
            effort_index = i
            break
        elif t["category"] == "cognitive" and t["label"].lower() == CURRENT_COGNITIVE_MODE.split()[0].lower():
            effort_index = i
            break

    COMPUTE_NODE_STATUS = "[🔴 Offline]"

    async def poll_compute_node(app: Application[None]) -> None:
        nonlocal COMPUTE_NODE_STATUS
        from axiom.services.ollama_monitor import OllamaHealthMonitor
        OllamaHealthMonitor.spawn_ollama_service()
        
        while True:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get("http://127.0.0.1:11434/api/version")
                    if resp.status_code == 200:
                        COMPUTE_NODE_STATUS = "[🟢 Local AI Engine Active]"
                        app.invalidate()
                        break
            except Exception:
                pass
            await asyncio.sleep(1.0)

    # 1. Window (Header)
    def get_header_text() -> HTML:
        return HTML(
            "<ansibrightcyan><b>"
            "  ██████╗  ██╗  ██╗ ██╗  ██████╗  ███╗   ███╗\n"
            " ██╔══██╗  ╚██╗██╔╝ ██║ ██╔═══██╗ ████╗ ████║\n"
            " ███████║   ╚███╔╝  ██║ ██║   ██║ ██╔████╔██║\n"
            " ██╔══██║   ██╔██╗  ██║ ██║   ██║ ██║╚██╔╝██║\n"
            " ██║  ██║  ██╔╝ ██╗ ██║ ╚██████╔╝ ██║ ╚═╝ ██║\n"
            " ╚═╝  ╚═╝  ╚═╝  ╚═╝ ╚═╝  ╚═════╝  ╚═╝     ╚═╝\n"
            "</b></ansibrightcyan>"
            f"  <ansicyan>Local-First  ·  AI Orchestration Framework  ·  {COMPUTE_NODE_STATUS}</ansicyan>"
        )

    header_window = Window(
        content=FormattedTextControl(get_header_text),
        height=8,
        dont_extend_height=True,
        style="class:header",
    )

    global CURRENT_SESSION_ID
    from axiom.db.memory import (
        get_latest_session_id,
        get_session_messages,
        create_session,
    )
    import uuid

    if not CURRENT_SESSION_ID:
        latest = get_latest_session_id()
        if latest:
            CURRENT_SESSION_ID = latest
        else:
            CURRENT_SESSION_ID = f"session_{uuid.uuid4().hex[:12]}"
            create_session(CURRENT_SESSION_ID, title="Default Session")

    historical = get_session_messages(CURRENT_SESSION_ID)
    if historical:
        chat_lines = [f"[Resumed session {CURRENT_SESSION_ID[:8]} with {len(historical)} messages]\n"]
        for msg in historical:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                chat_lines.append(f"\n❯ User:\n{content}\n")
            elif role == "assistant":
                chat_lines.append(f"\n◈ Axiom:\n{content}\n")
            elif role == "system":
                chat_lines.append(f"\n[System]\n{content}\n")
        initial_chat_text = "".join(chat_lines) + "\n"
    else:
        initial_chat_text = "Welcome to AXIOM. Ask anything, or type /help for commands.\n"

    # 2. TextArea (Scrollable chat history block)
    chat_history = TextArea(
        text=initial_chat_text,
        read_only=True,
        scrollbar=True,
        wrap_lines=True,
        style="class:chat-history",
        lexer=CognitiveLexer(),
    )
    chat_history.buffer.cursor_position = len(initial_chat_text)

    # Forward declaration for background sender
    async def send_to_backend(content_payload: str, app: Application[None]) -> None:
        global last_ai_response, current_tool_status
        system_messages = []
        if CURRENT_COGNITIVE_MODE != "Standard":
            mode_key = CURRENT_COGNITIVE_MODE.replace(" [BETA]", "").lower()
            cog_modes = get_cognitive_modes()
            if mode_key in cog_modes:
                system_messages.append({
                    "role": "system",
                    "content": cog_modes[mode_key].get("system_prompt", "COGNITIVE OVERRIDE ACTIVE.")
                })

        payload = {
            "messages": system_messages + [{"role": "user", "content": content_payload}],
            "model": "MiMo-V2.6",
            "stream": True,
            "session_id": CURRENT_SESSION_ID,
        }

        execution_trace.clear()
        full_response = ""
        current_tool_status = ""
        IN_THOUGHT = False
        app.invalidate()
        
        is_loading = True
        def clean_spinner():
            import re
            new_text = re.sub(r'\n\[⚙️.*?AXIOM is spinning up compute node\.\.\.\]', '', chat_history.text)
            chat_history.text = new_text
            chat_history.buffer.cursor_position = len(chat_history.text)
            
        async def spinner_loop():
            i = 0
            frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            while is_loading:
                frame = frames[i % len(frames)]
                msg = f"\n[⚙️ {frame} AXIOM is spinning up compute node...]"
                
                clean_spinner()
                chat_history.text += msg
                chat_history.buffer.cursor_position = len(chat_history.text)
                app.invalidate()
                
                await asyncio.sleep(0.1)
                i += 1
                
        spinner_task = asyncio.create_task(spinner_loop())

        try:
            from axiom.agents.native_orchestrator import NativeOrchestrator
            from axiom.core.plugins import get_tool_schemas
            
            payload["tools"] = get_tool_schemas(0)
            orchestrator = NativeOrchestrator()
            
            async for delta in orchestrator.generate_stream(payload):
                if "tool_calls" in delta:
                    execution_trace.append(delta["tool_calls"])
                    for tc in delta["tool_calls"]:
                        if "function" in tc and "name" in tc["function"]:
                            tool_name = tc["function"]["name"]
                            msg = TOOL_STATE_MAP.get(tool_name, "Working...")
                            current_tool_status = msg
                            chat_history.text += f"  [{msg}]\n"
                            chat_history.buffer.cursor_position = len(chat_history.text)
                            app.invalidate()
                elif "content" in delta:
                    if is_loading:
                        is_loading = False
                        spinner_task.cancel()
                        clean_spinner()
                    current_tool_status = ""
                    chunk = delta["content"]
                    full_response += chunk
                    
                    if "<think>" in chunk:
                        IN_THOUGHT = True
                        chunk = chunk.replace("<think>", "\u200b")
                    if "</think>" in chunk:
                        IN_THOUGHT = False
                        chunk = chunk.replace("</think>", "\u200c\n\n───\n\n")
                        
                    chat_history.text += chunk
                    chat_history.buffer.cursor_position = len(chat_history.text)
                    app.invalidate()
            last_ai_response = full_response
            chat_history.text += "\n"
            chat_history.buffer.cursor_position = len(chat_history.text)
            app.invalidate()
        except httpx.RequestError as exc:
            chat_history.text += f"\n⚠️ [FastAPI Error] Could not reach local compute node: {exc}\n"
            chat_history.buffer.cursor_position = len(chat_history.text)
        except Exception as exc:
            chat_history.text += f"\n⚠️ [Error] Unexpected error: {exc}\n"
            chat_history.buffer.cursor_position = len(chat_history.text)
        finally:
            is_loading = False
            if 'spinner_task' in locals():
                spinner_task.cancel()
            clean_spinner()
            current_tool_status = ""
            app.invalidate()

    # 3. TextArea (Input field for user prompt)
    def handle_accept(buff: Any) -> bool:
        global last_ai_response, CURRENT_EFFORT, CURRENT_COGNITIVE_MODE, active_modal, effort_index
        text = buff.text.strip()
        buff.text = ""
        if not text:
            return False

        if text.startswith("/"):
            parts = text.split()
            cmd = parts[0].lower()
            if cmd in ("/quit", "/exit"):
                get_app().exit()
                return False
            if cmd == "/clear":
                chat_history.text = ""
                return False
            if cmd == "/new":
                CURRENT_SESSION_ID = f"session_{uuid.uuid4().hex[:12]}"
                create_session(CURRENT_SESSION_ID, title="New Session")
                chat_history.text = f"[Started new session {CURRENT_SESSION_ID[:8]}]\n"
                chat_history.buffer.cursor_position = len(chat_history.text)
                get_app().invalidate()
                return False
            if cmd == "/cwd":
                chat_history.text += f"\n[CWD] {Path.cwd()}\n"
                chat_history.buffer.cursor_position = len(chat_history.text)
                return False
            if cmd == "/ver":
                chat_history.text += f"\n[Version] AXIOM TUI {VERSION}\n"
                chat_history.buffer.cursor_position = len(chat_history.text)
                return False
            if cmd == "/help":
                lines = [f"  {k:<10} - {v}" for k, v in COMMAND_REGISTRY.items()]
                chat_history.text += "\n[Commands]\n" + "\n".join(lines) + "\n"
                chat_history.buffer.cursor_position = len(chat_history.text)
                return False
            if cmd == "/copy":
                if not last_ai_response:
                    chat_history.text += "\n[Copy] No response to copy.\n"
                else:
                    try:
                        subprocess.run(["wl-copy"], input=last_ai_response.encode("utf-8"), check=True)
                        chat_history.text += "\n[Copy] ✓ Copied last response to clipboard.\n"
                    except Exception as e:
                        chat_history.text += f"\n[Copy] Failed: {e}\n"
                chat_history.buffer.cursor_position = len(chat_history.text)
                return False
            
            if cmd == "/model":
                MODAL_VISIBLE = True
                active_modal = "model"
                input_field.text = ""
                input_field.read_only = True
                get_app().layout.focus(modal_search_field)
                get_app().invalidate()
                return False
            if cmd == "/effort":
                if len(parts) > 1:
                    arg = parts[1].lower()
                    for i, t in enumerate(EFFORT_TIERS):
                        if t["label"].lower() == arg:
                            effort_index = i
                            if t["category"] == "compute":
                                CURRENT_EFFORT = t["label"] if t["id"] == "ultra" else t["label"].capitalize()
                                CURRENT_COGNITIVE_MODE = "Standard"
                            else:
                                CURRENT_COGNITIVE_MODE = t["label"].capitalize() + " [BETA]"
                                if t["id"] == "adhd":
                                    CURRENT_COGNITIVE_MODE = "ADHD [BETA]"
                                elif t["id"] == "overthinking":
                                    CURRENT_COGNITIVE_MODE = "Overthinking [BETA]"
                            chat_history.text += f"\n[Effort] Set to {t['label']}\n"
                            chat_history.buffer.cursor_position = len(chat_history.text)
                            get_app().invalidate()
                            return False
                MODAL_VISIBLE = True
                active_modal = "effort"
                get_app().invalidate()
                return False
            if cmd == "/mode":
                modes = ["Standard", "Overthinking [BETA]", "ADHD [BETA]"]
                idx = modes.index(CURRENT_COGNITIVE_MODE) if CURRENT_COGNITIVE_MODE in modes else 0
                CURRENT_COGNITIVE_MODE = modes[(idx + 1) % len(modes)]
                chat_history.text += f"\n[Mode] Switched to {CURRENT_COGNITIVE_MODE}\n"
                chat_history.buffer.cursor_position = len(chat_history.text)
                get_app().invalidate()
                return False

            chat_history.text += f"\n[Unknown Command] {text}\n"
            chat_history.buffer.cursor_position = len(chat_history.text)
            return False

        chat_history.text += f"\n❯ User:\n{text}\n\n◈ Axiom:\n"
        chat_history.buffer.cursor_position = len(chat_history.text)
        app = get_app()
        app.create_background_task(send_to_backend(text, app))
        return False

    input_field = TextArea(
        height=1,
        prompt="  ❯ ",
        multiline=False,
        wrap_lines=False,
        accept_handler=handle_accept,
        completer=SlashCommandCompleter(),
        complete_while_typing=True,
        style="class:input-field",
    )

    # 4. Window (Footer/Status bar)
    def get_footer_text() -> HTML:
        from axiom.core.ipc import ACTIVE_DAEMONS
        from axiom.core.scheduler import get_active_jobs
        cwd = str(Path.cwd())
        tool_status = f"  <ansiyellow>{current_tool_status}</ansiyellow>" if current_tool_status else ""
        num_daemons = len(ACTIVE_DAEMONS)
        daemon_str = f"<ansidarkgray>|</ansidarkgray>  <ansibrightcyan>Daemons:</ansibrightcyan> <ansibrightred>{num_daemons}</ansibrightred>  " if num_daemons > 0 else f"<ansidarkgray>|</ansidarkgray>  <ansibrightcyan>Daemons:</ansibrightcyan> <ansigray>0</ansigray>  "
        num_cron = len(get_active_jobs())
        cron_str = f"<ansidarkgray>|</ansidarkgray>  <ansibrightcyan>Cron:</ansibrightcyan> <ansimagenta>{num_cron}</ansimagenta>  " if num_cron > 0 else f"<ansidarkgray>|</ansidarkgray>  <ansibrightcyan>Cron:</ansibrightcyan> <ansigray>0</ansigray>  "
        status_line = (
            f" <ansigray>{cwd}</ansigray>  "
            f"<ansidarkgray>|</ansidarkgray>  <ansibrightcyan>Session:</ansibrightcyan> <ansigreen>{CURRENT_SESSION_ID[:8]}</ansigreen>  "
            f"<ansidarkgray>|</ansidarkgray>  <ansibrightcyan>Mode:</ansibrightcyan> <ansiwarning>{CURRENT_COGNITIVE_MODE}</ansiwarning>  "
            f"<ansidarkgray>|</ansidarkgray>  <ansibrightcyan>Compute:</ansibrightcyan> <ansimagenta>{CURRENT_EFFORT}</ansimagenta>  "
            f"{daemon_str}"
            f"{cron_str}"
            f"<ansidarkgray>|</ansidarkgray>  <ansidarkgray>{VERSION}</ansidarkgray>{tool_status}"
        )
        hotkeys_line = (
            " <ansidarkgray>[tab]</ansidarkgray> <ansibrightwhite>agents</ansibrightwhite>   "
            "<ansidarkgray>[ctrl+p]</ansidarkgray> <ansibrightwhite>commands</ansibrightwhite>   "
            "<ansidarkgray>[ctrl+m]</ansidarkgray> <ansibrightwhite>mode</ansibrightwhite>   "
            "<ansidarkgray>[ctrl+e]</ansidarkgray> <ansibrightwhite>effort</ansibrightwhite>   "
            "<ansidarkgray>[ctrl+o]</ansidarkgray> <ansibrightwhite>trace</ansibrightwhite>   "
            "<ansidarkgray>[ctrl+c]</ansidarkgray> <ansibrightwhite>quit</ansibrightwhite>"
        )
        return HTML(f"{hotkeys_line}\n{status_line}")

    footer_window = Window(
        content=FormattedTextControl(get_footer_text),
        height=2,
        dont_extend_height=True,
        style="class:footer",
    )

    # -----------------------------------------------------------------------
    # Modal Float Layout
    # -----------------------------------------------------------------------
    @Condition
    def is_modal_open() -> bool:
        return MODAL_VISIBLE or active_modal is not None

    @Condition
    def is_effort_modal_open() -> bool:
        return MODAL_VISIBLE or active_modal == "effort"

    @Condition
    def is_model_modal_open() -> bool:
        return MODAL_VISIBLE and active_modal == "model"


    def handle_modal_search_change(buff):
        global filtered_model_list, model_index
        query = buff.text.lower()
        filtered_model_list = [m for m in model_list if query in m.lower()]
        model_index = max(0, min(model_index, len(filtered_model_list) - 1))
        get_app().invalidate()

    modal_search_field = TextArea(
        height=1,
        prompt="  Search: ",
        multiline=False,
        style="class:system-alert",
    )
    modal_search_field.buffer.on_text_changed += handle_modal_search_change

    modal_kb = KeyBindings()
    @modal_kb.add("up")
    def _model_up(event: Any) -> None:
        global model_index
        model_index = max(0, model_index - 1)
        event.app.invalidate()
        
    @modal_kb.add("down")
    def _model_down(event: Any) -> None:
        global model_index
        model_index = min(len(filtered_model_list) - 1, model_index + 1)
        event.app.invalidate()
        
    @modal_kb.add("left")
    def _model_effort_left(event: Any) -> None:
        global effort_index
        effort_index = max(0, effort_index - 1)
        event.app.invalidate()

    @modal_kb.add("right")
    def _model_effort_right(event: Any) -> None:
        global effort_index
        effort_index = min(len(EFFORT_TIERS) - 1, effort_index + 1)
        event.app.invalidate()
        
    @modal_kb.add("enter")
    def _model_confirm(event: Any) -> None:
        global CURRENT_EFFORT, CURRENT_COGNITIVE_MODE, MODAL_VISIBLE, active_modal
        if filtered_model_list and model_index < len(filtered_model_list):
            selected_model = filtered_model_list[model_index]
            config = get_config()
            config.ollama_model = selected_model
            tier = EFFORT_TIERS[effort_index]
            setattr(config, "effort_tier", tier["id"])
            config.save()
        tier = EFFORT_TIERS[effort_index]
        if tier["category"] == "compute":
            CURRENT_EFFORT = tier["label"] if tier["id"] == "ultra" else tier["label"].capitalize()
            CURRENT_COGNITIVE_MODE = "Standard"
        else:
            CURRENT_COGNITIVE_MODE = tier["label"].capitalize() + " [BETA]"
            if tier["id"] == "adhd":
                CURRENT_COGNITIVE_MODE = "ADHD [BETA]"
            elif tier["id"] == "overthinking":
                CURRENT_COGNITIVE_MODE = "Overthinking [BETA]"
        MODAL_VISIBLE = False
        active_modal = None
        modal_search_field.text = ""
        input_field.read_only = False
        input_field.text = ""
        event.app.layout.focus(input_field)
        event.app.invalidate()

    @modal_kb.add("escape")
    def _model_escape(event: Any) -> None:
        global MODAL_VISIBLE, active_modal
        MODAL_VISIBLE = False
        active_modal = None
        modal_search_field.text = ""
        input_field.read_only = False
        input_field.text = ""
        event.app.layout.focus(input_field)
        event.app.invalidate()

    modal_search_field.control.key_bindings = modal_kb

    modal_frame = Frame(
        body=HSplit([
            modal_search_field,
            Window(content=FormattedTextControl(get_modal_content))
        ]),
        title=get_modal_title, 
        style="class:modal-frame"
    )

    modal_float = Float(
        content=ConditionalContainer(modal_frame, filter=is_modal_open)
    )

    ask_human_visible = False
    ask_human_prompt_id = ""
    ask_human_question = ""
    
    INTERRUPT_QUEUE = asyncio.Queue()
    ask_human_done_event = asyncio.Event()

    def handle_ask_human_accept(buff):
        nonlocal ask_human_visible, ask_human_prompt_id
        from axiom.core.ipc import PENDING_PROMPTS
        text = buff.text
        buff.text = ""
        ask_human_visible = False
        
        if ask_human_prompt_id in PENDING_PROMPTS:
            f = PENDING_PROMPTS[ask_human_prompt_id]
            if not f.done():
                f.set_result(text)
                
        ask_human_done_event.set()
        
        get_app().layout.focus(input_field)
        get_app().invalidate()
        return False

    ask_human_input = TextArea(
        height=1,
        prompt="  ❯ ",
        multiline=False,
        wrap_lines=False,
        accept_handler=handle_ask_human_accept,
        style="class:input-field",
    )

    def get_ask_human_text():
        return FormattedText([("class:system-alert", f"\n ✋ Agent Requires Input:\n\n  {ask_human_question}\n\n")])

    ask_human_window = HSplit([
        Window(content=FormattedTextControl(get_ask_human_text), height=5),
        ask_human_input
    ])

    ask_human_frame = Frame(ask_human_window, title="Human Interrupt", style="class:modal-frame")

    @Condition
    def is_ask_human_open():
        return ask_human_visible

    ask_human_float = Float(
        content=ConditionalContainer(ask_human_frame, filter=is_ask_human_open),
    )

    # -----------------------------------------------------------------------
    # Root FloatContainer & Main Body HSplit
    # -----------------------------------------------------------------------
    main_body = HSplit([
        header_window,
        chat_history,
        input_field,
        footer_window,
    ])

    root_container = FloatContainer(
        content=main_body,
        floats=[
            modal_float, 
            ask_human_float,
            Float(xcursor=True, ycursor=True, content=CompletionsMenu(max_height=10, scroll_offset=1))
        ],
    )

    # -----------------------------------------------------------------------
    # Keybindings
    # -----------------------------------------------------------------------
    kb = KeyBindings()

    @kb.add("c-c")
    def _exit_key(event: Any) -> None:
        event.app.exit()

    @kb.add("tab")
    def _agents_key(event: Any) -> None:
        global active_modal, MODAL_VISIBLE
        active_modal = None if active_modal == "agents" else "agents"
        MODAL_VISIBLE = active_modal is not None
        if not MODAL_VISIBLE:
            event.app.layout.focus(input_field)
        event.app.invalidate()

    @kb.add("c-p")
    def _commands_key(event: Any) -> None:
        global active_modal, MODAL_VISIBLE
        active_modal = None if active_modal == "commands" else "commands"
        MODAL_VISIBLE = active_modal is not None
        if not MODAL_VISIBLE:
            event.app.layout.focus(input_field)
        event.app.invalidate()

    @kb.add("c-o")
    def _trace_key(event: Any) -> None:
        global active_modal, MODAL_VISIBLE
        active_modal = None if active_modal == "trace" else "trace"
        MODAL_VISIBLE = active_modal is not None
        if not MODAL_VISIBLE:
            event.app.layout.focus(input_field)
        event.app.invalidate()

    @kb.add("c-t")
    def _mode_key(event: Any) -> None:
        global CURRENT_COGNITIVE_MODE
        modes = ["Standard", "Overthinking [BETA]", "ADHD [BETA]"]
        idx = modes.index(CURRENT_COGNITIVE_MODE) if CURRENT_COGNITIVE_MODE in modes else 0
        CURRENT_COGNITIVE_MODE = modes[(idx + 1) % len(modes)]
        event.app.invalidate()
    @kb.add("c-e")
    def _effort_key(event: Any) -> None:
        global MODAL_VISIBLE, active_modal
        MODAL_VISIBLE = not MODAL_VISIBLE
        active_modal = "effort" if MODAL_VISIBLE else None
        if not MODAL_VISIBLE:
            event.app.layout.focus(input_field)
        event.app.invalidate()

    @kb.add("escape", filter=is_modal_open)
    def _close_modal_key(event: Any) -> None:
        global MODAL_VISIBLE, active_modal
        MODAL_VISIBLE = False
        active_modal = None
        modal_search_field.text = ""
        input_field.read_only = False
        input_field.text = ""
        event.app.layout.focus(input_field)
        event.app.invalidate()

    @kb.add("left", filter=is_effort_modal_open)
    def _effort_left_key(event: Any) -> None:
        global effort_index
        effort_index = max(0, effort_index - 1)
        event.app.invalidate()

    @kb.add("right", filter=is_effort_modal_open)
    def _effort_right_key(event: Any) -> None:
        global effort_index
        effort_index = min(len(EFFORT_TIERS) - 1, effort_index + 1)
        event.app.invalidate()

    @kb.add("enter", filter=is_effort_modal_open)
    def _effort_confirm_key(event: Any) -> None:
        global CURRENT_EFFORT, CURRENT_COGNITIVE_MODE, MODAL_VISIBLE, active_modal
        tier = EFFORT_TIERS[effort_index]
        if tier["category"] == "compute":
            CURRENT_EFFORT = tier["label"] if tier["id"] == "ultra" else tier["label"].capitalize()
            CURRENT_COGNITIVE_MODE = "Standard"
        else:
            CURRENT_COGNITIVE_MODE = tier["label"].capitalize() + " [BETA]"
            if tier["id"] == "adhd":
                CURRENT_COGNITIVE_MODE = "ADHD [BETA]"
            elif tier["id"] == "overthinking":
                CURRENT_COGNITIVE_MODE = "Overthinking [BETA]"
        MODAL_VISIBLE = False
        active_modal = None
        event.app.layout.focus(input_field)
        event.app.invalidate()

    @kb.add("pageup")
    def _page_up_key(event: Any) -> None:
        chat_history.buffer.cursor_up(count=10)

    @kb.add("pagedown")
    def _page_down_key(event: Any) -> None:
        chat_history.buffer.cursor_down(count=10)

    # -----------------------------------------------------------------------
    # Styling
    # -----------------------------------------------------------------------
    style = Style.from_dict({
        "header": "#00ffff",
        "chat-history": "#ffffff",
        "input-field": "#ffffff bold",
        "footer": "#888888",
        "modal": "bg:#0d0d1a #ffffff",
        "modal-frame": "#ff00ff",
        "modal-text": "#ffffff",
        "reasoning": "ansigray italic",
        "system-alert": "ansibrightcyan bold",
        "pipeline-step": "ansicyan",
        "cron-alert": "ansimagenta bold",
        "critical-alert": "ansired bold",

        "content": "default",
    })

    layout = Layout(root_container, focused_element=input_field)

    app: Application[None] = Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        full_screen=True,
    )
    
    async def listen_to_bus():
        from axiom.core.ipc import SYSTEM_BUS
        while True:
            message = await SYSTEM_BUS.get()
            if isinstance(message, dict) and message.get("type") == "human_interrupt":
                await INTERRUPT_QUEUE.put(message)
            else:
                chat_history.text += f"\n{message}\n"
                chat_history.buffer.cursor_position = len(chat_history.text)
                app.invalidate()
                
    async def process_interrupts():
        nonlocal ask_human_visible, ask_human_prompt_id, ask_human_question
        while True:
            message = await INTERRUPT_QUEUE.get()
            ask_human_prompt_id = message["prompt_id"]
            ask_human_question = message["question"]
            ask_human_visible = True
            ask_human_done_event.clear()
            app.layout.focus(ask_human_input)
            app.invalidate()
            
            await ask_human_done_event.wait()
            
    app.create_background_task(listen_to_bus())
    app.create_background_task(process_interrupts())
    app.create_background_task(poll_compute_node(app))

    return app



async def fetch_local_models():
    global model_list, filtered_model_list, model_index
    try:
        config = get_config()
        url = f"{config.ollama_base_url}/api/tags"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                model_list = [m["name"] for m in data.get("models", [])]
            else:
                model_list = ["Error: Could not fetch models"]
    except Exception:
        model_list = ["No Ollama instance found"]
    
    filtered_model_list = model_list.copy()
    model_index = 0


async def background_animation_loop(app: Application[None]) -> None:
    """Procedural animation loop for ULTRA mode."""
    while True:
        if (MODAL_VISIBLE or active_modal == "effort") and EFFORT_TIERS[effort_index]["id"] == "ultra":
            app.invalidate()
        await asyncio.sleep(0.05)


async def async_run_tui() -> None:
    """Run the TUI application asynchronously."""
    app = create_tui_app()
    app.create_background_task(fetch_local_models())
    app.create_background_task(background_animation_loop(app))
    await app.run_async()


def run_tui() -> None:
    """Entry point — block on the asynchronous full-screen TUI application."""
    asyncio.run(async_run_tui())


if __name__ == "__main__":
    run_tui()
