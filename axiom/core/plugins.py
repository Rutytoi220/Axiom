import os
import sys
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Callable, Awaitable, Optional

TOOLS_DIR = Path.home() / ".config" / "axiom" / "tools.d"

_schemas: List[Dict[str, Any]] = []
_rings: Dict[str, int] = {}
_executors: Dict[str, Callable[..., Awaitable[str]]] = {}
_tui_hints: Dict[str, str] = {}

def load_plugins() -> None:
    global _schemas, _executors, _tui_hints
    _schemas.clear()
    _rings.clear()
    _executors.clear()
    _tui_hints.clear()

    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Ensure core semantic memory and Tier 1 OS tools are provisioned
    provisions = [
        (
            TOOLS_DIR / "remember_fact.py",
            (
                "import json\n"
                "from axiom.tools.memory import RememberFactTool\n\n"
                "_tool = RememberFactTool()\n\n"
                "TOOL_SCHEMA = {\n"
                '    "type": "function",\n'
                '    "function": {\n'
                '        "name": _tool.name,\n'
                '        "description": _tool.description,\n'
                '        "parameters": _tool.schema,\n'
                "    }\n"
                "}\n"
                'TUI_HINT = "🧠 Remembering fact in semantic memory..."\n'
                "REQUIRED_RING = 0\n\n"
                "async def execute(fact: str = '', **kwargs) -> str:\n"
                '    params = {"fact": fact, **kwargs}\n'
                "    res = await _tool.execute(params)\n"
                "    return json.dumps(res.to_dict(tool=_tool.name, arguments=params))\n"
            ),
        ),
        (
            TOOLS_DIR / "manage_system_process.py",
            (
                "import json\n"
                "from axiom.tools.os_system import ManageSystemProcessTool\n\n"
                "_tool = ManageSystemProcessTool()\n\n"
                "TOOL_SCHEMA = {\n"
                '    "type": "function",\n'
                '    "function": {\n'
                '        "name": _tool.name,\n'
                '        "description": _tool.description,\n'
                '        "parameters": _tool.schema,\n'
                "    }\n"
                "}\n"
                'TUI_HINT = "⚙️ Managing Linux system processes..."\n'
                "REQUIRED_RING = 0\n\n"
                "async def execute(action: str = 'list', target: str = '', signal: int = 15, **kwargs) -> str:\n"
                '    params = {"action": action, "target": target, "signal": signal, **kwargs}\n'
                "    res = await _tool.execute(params)\n"
                "    return json.dumps(res.to_dict(tool=_tool.name, arguments=params))\n"
            ),
        ),
        (
            TOOLS_DIR / "manage_system_clipboard.py",
            (
                "import json\n"
                "from axiom.tools.os_system import ManageSystemClipboardTool\n\n"
                "_tool = ManageSystemClipboardTool()\n\n"
                "TOOL_SCHEMA = {\n"
                '    "type": "function",\n'
                '    "function": {\n'
                '        "name": _tool.name,\n'
                '        "description": _tool.description,\n'
                '        "parameters": _tool.schema,\n'
                "    }\n"
                "}\n"
                'TUI_HINT = "📋 Managing system clipboard..."\n'
                "REQUIRED_RING = 0\n\n"
                "async def execute(action: str = 'read', content: str = '', **kwargs) -> str:\n"
                '    params = {"action": action, "content": content, **kwargs}\n'
                "    res = await _tool.execute(params)\n"
                "    return json.dumps(res.to_dict(tool=_tool.name, arguments=params))\n"
            ),
        ),
        (
            TOOLS_DIR / "query_system_journal.py",
            (
                "import json\n"
                "from axiom.tools.os_system import QuerySystemJournalTool\n\n"
                "_tool = QuerySystemJournalTool()\n\n"
                "TOOL_SCHEMA = {\n"
                '    "type": "function",\n'
                '    "function": {\n'
                '        "name": _tool.name,\n'
                '        "description": _tool.description,\n'
                '        "parameters": _tool.schema,\n'
                "    }\n"
                "}\n"
                'TUI_HINT = "📜 Querying systemd journal logs..."\n'
                "REQUIRED_RING = 0\n\n"
                "async def execute(lines: int = 30, unit: str = '', priority: str = '', **kwargs) -> str:\n"
                '    params = {"lines": lines, "unit": unit, "priority": priority, **kwargs}\n'
                "    res = await _tool.execute(params)\n"
                "    return json.dumps(res.to_dict(tool=_tool.name, arguments=params))\n"
            ),
        ),
        (
            TOOLS_DIR / "manage_media_playback.py",
            (
                "import json\n"
                "from axiom.tools.os_desktop import ManageMediaPlaybackTool\n\n"
                "_tool = ManageMediaPlaybackTool()\n\n"
                "TOOL_SCHEMA = {\n"
                '    "type": "function",\n'
                '    "function": {\n'
                '        "name": _tool.name,\n'
                '        "description": _tool.description,\n'
                '        "parameters": _tool.schema,\n'
                "    }\n"
                "}\n"
                'TUI_HINT = "🎵 Controlling desktop media & audio..."\n'
                "REQUIRED_RING = 0\n\n"
                "async def execute(action: str = 'status', player: str = '', value: str = '', **kwargs) -> str:\n"
                '    params = {"action": action, "player": player, "value": value, **kwargs}\n'
                "    res = await _tool.execute(params)\n"
                "    return json.dumps(res.to_dict(tool=_tool.name, arguments=params))\n"
            ),
        ),
        (
            TOOLS_DIR / "manage_workspace_file.py",
            (
                "import json\n"
                "from axiom.tools.workspace_file import ManageWorkspaceFileTool\n\n"
                "_tool = ManageWorkspaceFileTool()\n\n"
                "TOOL_SCHEMA = {\n"
                '    "type": "function",\n'
                '    "function": {\n'
                '        "name": _tool.name,\n'
                '        "description": _tool.description,\n'
                '        "parameters": _tool.schema,\n'
                "    }\n"
                "}\n"
                'TUI_HINT = "📁 Safely managing workspace file..."\n'
                "REQUIRED_RING = 0\n\n"
                "async def execute(action: str = 'read', path: str = '', content: str = '', search_text: str = '', replace_text: str = '', max_lines: int = 200, **kwargs) -> str:\n"
                '    params = {"action": action, "path": path, "content": content, "search_text": search_text, "replace_text": replace_text, "max_lines": max_lines, **kwargs}\n'
                "    res = await _tool.execute(params)\n"
                "    return json.dumps(res.to_dict(tool=_tool.name, arguments=params))\n"
            ),
        ),
        (
            TOOLS_DIR / "send_desktop_notification.py",
            (
                "import json\n"
                "from axiom.tools.os_desktop import SendDesktopNotificationTool\n\n"
                "_tool = SendDesktopNotificationTool()\n\n"
                "TOOL_SCHEMA = {\n"
                '    "type": "function",\n'
                '    "function": {\n'
                '        "name": _tool.name,\n'
                '        "description": _tool.description,\n'
                '        "parameters": _tool.schema,\n'
                "    }\n"
                "}\n"
                'TUI_HINT = "🔔 Sending native desktop notification..."\n'
                "REQUIRED_RING = 0\n\n"
                "async def execute(title: str = '', message: str = '', urgency: str = 'normal', app_name: str = 'AXIOM', **kwargs) -> str:\n"
                '    params = {"title": title, "message": message, "urgency": urgency, "app_name": app_name, **kwargs}\n'
                "    res = await _tool.execute(params)\n"
                "    return json.dumps(res.to_dict(tool=_tool.name, arguments=params))\n"
            ),
        ),
        (
            TOOLS_DIR / "inspect_network.py",
            (
                "import json\n"
                "from axiom.tools.os_system import InspectNetworkTool\n\n"
                "_tool = InspectNetworkTool()\n\n"
                "TOOL_SCHEMA = {\n"
                '    "type": "function",\n'
                '    "function": {\n'
                '        "name": _tool.name,\n'
                '        "description": _tool.description,\n'
                '        "parameters": _tool.schema,\n'
                "    }\n"
                "}\n"
                'TUI_HINT = "🌐 Inspecting network interfaces & latency..."\n'
                "REQUIRED_RING = 0\n\n"
                "async def execute(check_target: str = '1.1.1.1', **kwargs) -> str:\n"
                '    params = {"check_target": check_target, **kwargs}\n'
                "    res = await _tool.execute(params)\n"
                "    return json.dumps(res.to_dict(tool=_tool.name, arguments=params))\n"
            ),
        ),
        (
            TOOLS_DIR / "execute_command.py",
            (
                "import subprocess\n\n"
                "TOOL_SCHEMA = {\n"
                '    "type": "function",\n'
                '    "function": {\n'
                '        "name": "execute_command",\n'
                '        "description": "Executes a shell command via bash and returns stdout and stderr.",\n'
                '        "parameters": {\n'
                '            "type": "object",\n'
                '            "properties": {\n'
                '                "command": {"type": "string", "description": "Command to execute"}\n'
                '            },\n'
                '            "required": ["command"]\n'
                '        }\n'
                '    }\n'
                "}\n"
                'TUI_HINT = "⚙️ Executing system command..."\n'
                "REQUIRED_RING = 0\n\n"
                "async def execute(command: str = '', **kwargs) -> str:\n"
                "    try:\n"
                "        proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)\n"
                "        body = (proc.stdout or '') + (proc.stderr or '')\n"
                '        return f"Exit code {proc.returncode}\\n{body}".strip() if body else f"Exit code {proc.returncode}"\n'
                "    except Exception as e:\n"
                '        return f"Error executing command: {e}"\n'
            ),
        ),
    ]
    for target_file, code_content in provisions:
        if not target_file.exists():
            try:
                target_file.write_text(code_content, encoding="utf-8")
            except Exception:
                pass

    for path in TOOLS_DIR.glob("*.py"):
        if path.name.startswith("__"):
            continue
            
        module_name = f"axiom.dynamic_tools.{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                
                if hasattr(mod, "TOOL_SCHEMA") and hasattr(mod, "execute"):
                    schema = getattr(mod, "TOOL_SCHEMA")
                    fn = schema.setdefault("function", {})
                    params = fn.get("parameters")
                    if not params or not isinstance(params, dict) or params.get("type") in ("", None) or params.get("properties") is None:
                        fn["parameters"] = {"type": "object", "properties": {}}
                    name = fn["name"]
                    _schemas.append(schema)
                    _executors[name] = getattr(mod, "execute")
                    _rings[name] = getattr(mod, "REQUIRED_RING", 0)
                    
                    if hasattr(mod, "TUI_HINT"):
                        _tui_hints[name] = getattr(mod, "TUI_HINT")
            except Exception as e:
                print(f"\033[1;31m[Warning] Failed to load plugin {path.name}: {e}\033[0m")

CORE_TOOLS = {
    "execute_command",
    "manage_desktop_window",
}

TIER_1_TOOLS = {
    "manage_system_process",
    "manage_system_clipboard",
    "query_system_journal",
    "manage_media_playback",
    "manage_workspace_file",
    "send_desktop_notification",
    "inspect_network",
}

TIER_2_TOOLS = {
    "interact_with_browser",
}


def filter_tool_schemas_by_tier(schemas: List[Dict[str, Any]], tier: str, is_browser: bool = False) -> List[Dict[str, Any]]:
    """Filter dynamic tool schemas based on the detected automation tier.

    - Always includes core system tools: execute_command, manage_desktop_window.
    - If Tier 1: includes Tier 1 tools (manage_system_process, manage_system_clipboard,
      query_system_journal, manage_media_playback, manage_workspace_file,
      send_desktop_notification, inspect_network).
    - If Tier 2: includes Tier 2 tools (interact_with_browser).
    - If Tier 3 / Ambiguous / General: includes the full registry.
    - If is_browser is True, interact_with_ui is strictly purged from exposed schemas.
    """
    tier_lower = (tier or "").lower().strip()
    if tier_lower in ("tier1", "tier1_ipc", "1"):
        allowed = CORE_TOOLS | TIER_1_TOOLS
        filtered = [s for s in schemas if (s.get("function", {}).get("name") or s.get("name")) in allowed]
        result = filtered if filtered else list(schemas)
    elif tier_lower in ("tier2", "tier2_browser", "2"):
        allowed = CORE_TOOLS | TIER_2_TOOLS
        filtered = [s for s in schemas if (s.get("function", {}).get("name") or s.get("name")) in allowed]
        result = filtered if filtered else list(schemas)
    else:
        result = list(schemas)

    if is_browser:
        result = [s for s in result if (s.get("function", {}).get("name") or s.get("name")) != "interact_with_ui"]

    return result


def get_tool_schemas(ring: int = 0, tier: Optional[str] = None, is_browser: bool = False) -> List[Dict[str, Any]]:
    if not _schemas:
        load_plugins()
    filtered = []
    for s in _schemas:
        fn = s.setdefault("function", {})
        params = fn.get("parameters")
        if not params or not isinstance(params, dict) or params.get("type") in ("", None) or params.get("properties") is None:
            fn["parameters"] = {"type": "object", "properties": {}}
        name = fn["name"]
        tool_ring = _rings.get(name, 0)
        # Ring 0 has access to everything. Ring 3 only has access to Ring 3+.
        if tool_ring >= ring:
            filtered.append(s)
    if tier or is_browser:
        filtered = filter_tool_schemas_by_tier(filtered, tier or "", is_browser=is_browser)
    return filtered

def get_tui_hints() -> Dict[str, str]:
    if not _tui_hints:
        load_plugins()
    return dict(_tui_hints)

TIER_TIMEOUTS: Dict[str, float] = {
    "interact_with_ui": 35.0,
    "vision": 35.0,
    "capture_som_screen": 35.0,
    "click_tag": 35.0,
    "interact_with_browser": 10.0,
}

def get_tier_timeout(tool_name: str) -> float:
    """Return execution latency budget for a given tool name:
    Tier 1 (CLI/OS): 8.0s
    Tier 2 (Browser Extension): 10.0s
    Tier 3 (VLM Grounding): 35.0s
    """
    return TIER_TIMEOUTS.get(tool_name, 8.0)

async def execute_tool(name: str, **kwargs) -> str:
    if not _executors:
        load_plugins()
    if name not in _executors:
        return f"Tool execution failed: Tool {name} not found in dynamic plugins."
    
    import asyncio
    func = _executors[name]
    
    def thread_worker():
        if asyncio.iscoroutinefunction(func):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(func(**kwargs))
            finally:
                loop.close()
        else:
            return func(**kwargs)
            
    timeout = get_tier_timeout(name)
    timeout_int = int(timeout)
    try:
        res = await asyncio.wait_for(
            asyncio.to_thread(thread_worker),
            timeout=timeout
        )
        return str(res)
    except (TimeoutError, asyncio.TimeoutError):
        return json.dumps({
            "success": False,
            "error": f"Tool execution timed out after {timeout_int}s. Try a faster Tier 1 command or verify active window.",
        })
    except Exception as e:
        return f"Tool execution failed: {e}"


def reload_plugin(path: Path) -> None:
    if not path.is_file() or not path.name.endswith(".py"):
        return
        
    module_name = f"axiom.dynamic_tools.{path.stem}"
    
    # Clean up sys.modules cache to force a fresh import
    if module_name in sys.modules:
        del sys.modules[module_name]
        
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
            
            if hasattr(mod, "TOOL_SCHEMA") and hasattr(mod, "execute"):
                schema = getattr(mod, "TOOL_SCHEMA")
                fn = schema.setdefault("function", {})
                params = fn.get("parameters")
                if not params or not isinstance(params, dict) or params.get("type") in ("", None) or params.get("properties") is None:
                    fn["parameters"] = {"type": "object", "properties": {}}
                name = fn["name"]
                
                # Remove existing schema if it exists
                global _schemas, _executors, _tui_hints
                _schemas = [s for s in _schemas if s["function"]["name"] != name]
                
                _schemas.append(schema)
                _executors[name] = getattr(mod, "execute")
                _rings[name] = getattr(mod, "REQUIRED_RING", 0)
                
                if hasattr(mod, "TUI_HINT"):
                    _tui_hints[name] = getattr(mod, "TUI_HINT")
                    
        except Exception as e:
            print(f"\033[1;31m[Warning] Failed to load plugin {path.name}: {e}\033[0m")
