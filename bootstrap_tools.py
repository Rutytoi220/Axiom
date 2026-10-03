import os
from pathlib import Path

TOOLS_DIR = Path.home() / ".config" / "axiom" / "tools.d"
TOOLS_DIR.mkdir(parents=True, exist_ok=True)

tools_map = {
    "file_ops.py": '''
import os

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Reads the text content of a file at the given path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"}
            },
            "required": ["path"]
        }
    }
}
TUI_HINT = "📄 Reading file..."

async def execute(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file {path}: {e}"
''',
    
    "write_file.py": '''
import os

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Writes text content to a file at the given path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write to"},
                "content": {"type": "string", "description": "Text content to write"}
            },
            "required": ["path", "content"]
        }
    }
}
TUI_HINT = "💾 Writing to disk..."

async def execute(path: str, content: str) -> str:
    try:
        dir_name = os.path.dirname(os.path.abspath(path))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}."
    except Exception as e:
        return f"Error writing file {path}: {e}"
''',

    "patch_file.py": '''
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "patch_file",
        "description": "Surgically replaces a specific block of code in an existing file. ALWAYS use this instead of write_file for modifying existing codebases to prevent file truncation. The search_block must perfectly match the existing file.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The exact target file path"},
                "search_block": {"type": "string", "description": "The exact block of code to be replaced"},
                "replace_block": {"type": "string", "description": "The new code that will replace the search_block"}
            },
            "required": ["path", "search_block", "replace_block"]
        }
    }
}
TUI_HINT = "🔨 Patching codebase..."

async def execute(path: str, search_block: str, replace_block: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            current_content = f.read()
        if search_block not in current_content:
            return "Error: search_block not found in file. You must match the exact whitespace, line breaks, and indentation of the original file. Try again."
        elif current_content.count(search_block) > 1:
            return "Error: search_block matches multiple locations in the file. You must include more surrounding context (lines above/below) to make the search_block uniquely identifiable. Try again."
        else:
            new_content = current_content.replace(search_block, replace_block)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"Successfully patched {path}."
    except Exception as e:
        return f"Error patching file {path}: {e}"
''',

    "bash_exec.py": '''
import subprocess

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "execute_bash",
        "description": "Executes a shell command via bash and returns stdout and stderr.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bash command to execute"}
            },
            "required": ["command"]
        }
    }
}
TUI_HINT = "⚙️ Executing system command..."

async def execute(command: str) -> str:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        output_parts = []
        if proc.stdout:
            output_parts.append(proc.stdout)
        if proc.stderr:
            output_parts.append(proc.stderr)
        body = "\\n".join(output_parts).strip()
        return f"Exit code {proc.returncode}\\n{body}".strip() if body else f"Exit code {proc.returncode}"
    except Exception as e:
        return f"Error executing command: {e}"
''',

    "list_containers.py": '''
import subprocess

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_containers",
        "description": "Lists all available Distrobox and Docker containers on the system.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
}
TUI_HINT = "📦 Scanning container environments..."

async def execute() -> str:
    output = []
    try:
        proc_dbx = subprocess.run(["distrobox", "list", "--no-color"], capture_output=True, text=True, timeout=10)
        output.append("=== Distrobox Containers ===")
        output.append(proc_dbx.stdout.strip() if proc_dbx.stdout else "No Distrobox containers found.")
    except Exception as e:
        output.append(f"Distrobox error: {e}")
    output.append("")
    try:
        proc_docker = subprocess.run(["docker", "ps", "--format", "table {{.Names}}\\t{{.Image}}\\t{{.Status}}"], capture_output=True, text=True, timeout=10)
        output.append("=== Docker Containers ===")
        output.append(proc_docker.stdout.strip() if proc_docker.stdout else "No Docker containers found.")
    except Exception as e:
        output.append(f"Docker error: {e}")
    return "\\n".join(output)
''',

    "exec_distrobox.py": '''
import subprocess

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "execute_in_distrobox",
        "description": "Executes a bash command inside a specific Distrobox container.",
        "parameters": {
            "type": "object",
            "properties": {
                "container_name": {"type": "string", "description": "Name of the Distrobox container"},
                "command": {"type": "string", "description": "Bash command to execute"}
            },
            "required": ["container_name", "command"]
        }
    }
}
TUI_HINT = "🐋 Executing in Distrobox..."

async def execute(container_name: str, command: str) -> str:
    try:
        proc = subprocess.run(
            ["distrobox-enter", "--name", container_name, "--headless", "--", "bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=120
        )
        res_body = "\\n".join(filter(None, [proc.stdout, proc.stderr])).strip()
        return f"Exit code {proc.returncode}\\n{res_body}".strip() if res_body else f"Exit code {proc.returncode}"
    except Exception as e:
        return f"Error executing in distrobox: {e}"
''',

    "exec_docker.py": '''
import subprocess

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "execute_in_docker",
        "description": "Executes a command inside a specific Docker container.",
        "parameters": {
            "type": "object",
            "properties": {
                "container_name": {"type": "string", "description": "Name of the Docker container"},
                "command": {"type": "string", "description": "Bash command to execute"}
            },
            "required": ["container_name", "command"]
        }
    }
}
TUI_HINT = "🐳 Executing in Docker..."

async def execute(container_name: str, command: str) -> str:
    try:
        proc = subprocess.run(
            ["docker", "exec", container_name, "bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=120
        )
        res_body = "\\n".join(filter(None, [proc.stdout, proc.stderr])).strip()
        return f"Exit code {proc.returncode}\\n{res_body}".strip() if res_body else f"Exit code {proc.returncode}"
    except Exception as e:
        return f"Error executing in docker: {e}"
''',

    "search_memory.py": '''
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_memory",
        "description": "Searches your past conversation history for keywords, code snippets, or context that is no longer in your active memory.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query keywords or phrases"},
                "session_id": {"type": "string", "description": "Optional session ID"}
            },
            "required": ["query"]
        }
    }
}
TUI_HINT = "🧠 Searching subconscious memory..."

async def execute(query: str, session_id: str = "") -> str:
    try:
        from axiom.db.memory import search_historical_context
        if session_id:
            results = search_historical_context(query, session_id)
            return "\\n".join(results) if results else "No relevant memories found."
        else:
            return "No active session to search."
    except Exception as e:
        return f"Error searching memory: {e}"
'''
}

for name, content in tools_map.items():
    with open(TOOLS_DIR / name, "w") as f:
        f.write(content.strip() + "\n")

print(f"Bootstrapped {len(tools_map)} tools to {TOOLS_DIR}")

desktop_tools = {
    "vision.py": '''
import json
from axiom.tools.vision import InteractWithUITool

_tool = InteractWithUITool()

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": _tool.name,
        "description": _tool.description,
        "parameters": _tool.schema
    }
}
TUI_HINT = "🎯 Interacting with UI..."
REQUIRED_RING = 0

async def execute(instruction: str, **kwargs) -> str:
    params = {"instruction": instruction, **kwargs}
    res = await _tool.execute(params)
    return json.dumps(res.to_dict())
'''
}

for name, content in desktop_tools.items():
    with open(TOOLS_DIR / name, "w") as f:
        f.write(content.strip() + "\n")


