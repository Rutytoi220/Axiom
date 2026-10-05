import os
import sys
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Callable, Awaitable

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
    
    # Ensure core semantic memory tool is provisioned
    rem_fact_file = TOOLS_DIR / "remember_fact.py"
    if not rem_fact_file.exists():
        rem_fact_code = (
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
        )
        try:
            rem_fact_file.write_text(rem_fact_code, encoding="utf-8")
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

def get_tool_schemas(ring: int = 0) -> List[Dict[str, Any]]:
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
    return filtered

def get_tui_hints() -> Dict[str, str]:
    if not _tui_hints:
        load_plugins()
    return dict(_tui_hints)

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
            
    try:
        res = await asyncio.wait_for(
            asyncio.to_thread(thread_worker),
            timeout=30.0
        )
        return str(res)
    except TimeoutError:
        return "Tool execution failed: Timeout after 30s"
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
