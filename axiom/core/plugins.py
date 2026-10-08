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
_capabilities: Dict[str, Any] = {}

def load_plugins() -> None:
    global _schemas, _executors, _tui_hints, _capabilities
    _schemas.clear()
    _rings.clear()
    _executors.clear()
    _tui_hints.clear()
    _capabilities.clear()

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
                "IS_CORE = True\n"
                "TIER = 0\n"
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

                    _capabilities[name] = _extract_capability(mod, name)
            except Exception as e:
                print(f"\033[1;31m[Warning] Failed to load plugin {path.name}: {e}\033[0m")

    # Autonomous Capability Indexing into persistent MemoryStore
    try:
        from axiom.memory.capability_indexer import index_tool_capabilities
        index_tool_capabilities()
    except Exception:
        pass


TIER_1_BUILTIN = {
    "manage_system_process",
    "manage_system_clipboard",
    "query_system_journal",
    "manage_media_playback",
    "manage_workspace_file",
    "send_desktop_notification",
    "inspect_network",
}


def _extract_capability(mod: Any, name: str):
    from axiom.tools.core import ToolCapability

    if mod is not None:
        if hasattr(mod, "CAPABILITY") and isinstance(mod.CAPABILITY, ToolCapability):
            return mod.CAPABILITY
        if hasattr(mod, "TIER"):
            try:
                tier = int(getattr(mod, "TIER", 1))
            except Exception:
                tier = 1
            is_core = bool(getattr(mod, "IS_CORE", tier == 0))
            requires_bridge = bool(getattr(mod, "REQUIRES_BRIDGE", tier == 2))
            requires_window = bool(getattr(mod, "REQUIRES_WINDOW", False))
            try:
                token_cost = int(getattr(mod, "TOKEN_COST", 150))
            except Exception:
                token_cost = 150
            return ToolCapability(
                tier=tier,
                is_core=is_core,
                requires_bridge=requires_bridge,
                requires_window=requires_window,
                token_cost=token_cost,
            )
        if hasattr(mod, "IS_CORE") and bool(getattr(mod, "IS_CORE")):
            return ToolCapability(
                tier=0,
                is_core=True,
                requires_bridge=bool(getattr(mod, "REQUIRES_BRIDGE", False)),
                requires_window=bool(getattr(mod, "REQUIRES_WINDOW", False)),
                token_cost=int(getattr(mod, "TOKEN_COST", 150)),
            )
        if hasattr(mod, "_tool") and hasattr(mod._tool, "capability"):
            cap = mod._tool.capability
            if name in ("manage_desktop_window", "interact_with_browser", "interact_with_ui") or name in TIER_1_BUILTIN:
                return cap
            if cap.is_core or cap.tier in (2, 3) or cap.requires_bridge:
                return cap

    # Heuristic fallback mapping by tool identifier
    if name in ("execute_command", "manage_desktop_window"):
        return ToolCapability(
            tier=0 if name == "execute_command" else 1,
            is_core=True,
            requires_bridge=False,
            requires_window=(name == "manage_desktop_window"),
            token_cost=150,
        )
    if name in TIER_1_BUILTIN:
        return ToolCapability(
            tier=1,
            is_core=False,
            requires_bridge=False,
            requires_window=False,
            token_cost=150,
        )
    if name == "interact_with_browser":
        return ToolCapability(
            tier=2,
            is_core=False,
            requires_bridge=True,
            requires_window=True,
            token_cost=250,
        )
    if name in ("interact_with_ui", "vision", "capture_som_screen", "som_click", "som_type", "som_key"):
        return ToolCapability(
            tier=3,
            is_core=False,
            requires_bridge=False,
            requires_window=True,
            token_cost=600,
        )
    return ToolCapability(
        tier=None,
        is_core=False,
        requires_bridge=False,
        requires_window=False,
        token_cost=150,
    )


def get_tool_capability(name: str):
    if not _capabilities and not _schemas:
        load_plugins()
    if name in _capabilities:
        return _capabilities[name]
    return _extract_capability(None, name)


def get_tool_capabilities() -> Dict[str, Any]:
    if not _capabilities and not _schemas:
        load_plugins()
    return dict(_capabilities)


class DynamicCapabilitySet(set):
    """Compatibility set proxy reflecting capability registry dynamically."""

    def __init__(self, filter_fn: Callable[[str, Any], bool], default_fallback: set):
        super().__init__(default_fallback)
        self._filter_fn = filter_fn
        self._default_fallback = set(default_fallback)

    def _sync(self) -> None:
        if _capabilities:
            res = {name for name, cap in _capabilities.items() if self._filter_fn(name, cap)}
            if res:
                self.clear()
                self.update(res)
                return
        self.clear()
        self.update(self._default_fallback)

    def __contains__(self, item: Any) -> bool:
        self._sync()
        return super().__contains__(item)

    def __iter__(self):
        self._sync()
        return super().__iter__()

    def __len__(self) -> int:
        self._sync()
        return super().__len__()

    def __or__(self, other: Any) -> set:
        self._sync()
        if isinstance(other, DynamicCapabilitySet):
            other._sync()
        return super().__or__(other)

    def __ror__(self, other: Any) -> set:
        self._sync()
        if isinstance(other, DynamicCapabilitySet):
            other._sync()
        return set(other) | set(self)

    def __and__(self, other: Any) -> set:
        self._sync()
        if isinstance(other, DynamicCapabilitySet):
            other._sync()
        return super().__and__(other)

    def __rand__(self, other: Any) -> set:
        self._sync()
        if isinstance(other, DynamicCapabilitySet):
            other._sync()
        return set(other) & set(self)

    def __sub__(self, other: Any) -> set:
        self._sync()
        if isinstance(other, DynamicCapabilitySet):
            other._sync()
        return super().__sub__(other)

    def __rsub__(self, other: Any) -> set:
        self._sync()
        if isinstance(other, DynamicCapabilitySet):
            other._sync()
        return set(other) - set(self)

    def __repr__(self) -> str:
        self._sync()
        return super().__repr__()


CORE_TOOLS = DynamicCapabilitySet(
    lambda n, c: getattr(c, "is_core", False) or getattr(c, "tier", None) == 0,
    {"execute_command", "manage_desktop_window"},
)

TIER_1_TOOLS = DynamicCapabilitySet(
    lambda n, c: getattr(c, "tier", None) == 1 and not getattr(c, "is_core", False),
    {
        "manage_system_process",
        "manage_system_clipboard",
        "query_system_journal",
        "manage_media_playback",
        "manage_workspace_file",
        "send_desktop_notification",
        "inspect_network",
    },
)

TIER_2_TOOLS = DynamicCapabilitySet(
    lambda n, c: getattr(c, "tier", None) == 2,
    {"interact_with_browser"},
)

TIER_3_TOOLS = DynamicCapabilitySet(
    lambda n, c: getattr(c, "tier", None) == 3,
    {"interact_with_ui"},
)


def filter_tool_schemas_by_tier(schemas: List[Dict[str, Any]], tier: str, is_browser: bool = False) -> List[Dict[str, Any]]:
    """Filter dynamic tool schemas based on the detected automation tier.

    - Always includes core system tools: execute_command, manage_desktop_window.
    - If Tier 1: includes Core + Tier 1 tools.
    - If Tier 2: includes Core + Tier 2 tools.
    - If Tier 3 / Ambiguous / General: includes the full registry.
    - If is_browser is True, interact_with_ui is strictly purged from exposed schemas.
    """
    tier_lower = (tier or "").lower().strip()
    if tier_lower in ("tier1", "tier1_ipc", "1"):
        target_tier = 1
    elif tier_lower in ("tier2", "tier2_browser", "2"):
        target_tier = 2
    else:
        target_tier = None

    if target_tier is not None:
        filtered = []
        for s in schemas:
            name = s.get("function", {}).get("name") or s.get("name")
            cap = get_tool_capability(name)
            if cap.is_core or cap.tier == 0 or cap.tier == target_tier:
                filtered.append(s)
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
                global _schemas, _executors, _tui_hints, _capabilities
                _schemas = [s for s in _schemas if s["function"]["name"] != name]
                
                _schemas.append(schema)
                _executors[name] = getattr(mod, "execute")
                _rings[name] = getattr(mod, "REQUIRED_RING", 0)
                _capabilities[name] = _extract_capability(mod, name)
                
                if hasattr(mod, "TUI_HINT"):
                    _tui_hints[name] = getattr(mod, "TUI_HINT")
                    
        except Exception as e:
            print(f"\033[1;31m[Warning] Failed to load plugin {path.name}: {e}\033[0m")

    try:
        from axiom.memory.capability_indexer import index_tool_capabilities
        index_tool_capabilities()
    except Exception:
        pass

