# AXIOM Quick Start Guide

Get up and running with AXIOM in 5 minutes.

## 1. Installation & CLI

The easiest way to use AXIOM is via the CLI:

```bash
cd /path/to/axiom
pip install -e .

# Start the CLI
axiom
```

You can chat with the orchestrator, or type `help` for commands like `status` and `tools`.

## 2. Using the API in Python

AXIOM is designed to be easily embedded in your own Python scripts.

### Basic Initialization

AXIOM's core components are the `Engine`, `SyncMemoryStore`, `ToolRegistry`, and `OrchestratorAgent`.

```python
import os
from axiom.core import Engine, shutdown_bridge
from axiom.memory import SyncMemoryStore
from axiom.llm import OllamaClient, OllamaConfig
from axiom.agents.orchestrator_agent import OrchestratorAgent
from axiom.tool_registry import ToolRegistry

# 1. Configure the LLM
model = os.environ.get("AXIOM_MODEL", "llama3:8b")
ollama = OllamaClient(OllamaConfig(model=model))

# 2. Setup Persistent Memory
# Note: Use an absolute path to avoid fragmentation
memory = SyncMemoryStore("/path/to/your/axiom.db", embedding_provider=ollama)

# 3. Setup the Engine & Registry
engine = Engine(memory=memory)
tool_registry = ToolRegistry(engine.registry)

# 4. Instantiate the Orchestrator
agent = OrchestratorAgent(
    tool_registry=tool_registry,
    event_bus=engine.event_bus,
    memory=memory,
    llm=ollama
)
```

### Running the Orchestrator

You can send tasks directly to the agent. It will automatically route to tools and generate a response.

```python
# Execute a task
result = agent.run("What is the meaning of life?", use_tools=True)

print(result.output)

# Always cleanly shut down the async bridge when finished
shutdown_bridge()
```

### Registering Built-in Tools

AXIOM comes with several built-in tools like `ShellTool`, `FileReadTool`, and `FileWriteTool`.

```python
from axiom.tools import ShellTool, FileReadTool, FileWriteTool

# Register tools with the registry
tool_registry.register(ShellTool())
tool_registry.register(FileReadTool(base_dir="."))
tool_registry.register(FileWriteTool(base_dir="."))

# Now the agent can interact with your file system
result = agent.run("Create a file called hello.txt saying hi!")
```

## 3. Creating Custom Tools

Creating a custom tool is as simple as inheriting from `BaseTool` and implementing `execute()`.

```python
import asyncio
from typing import Dict, Any
from axiom.tools import BaseTool, ToolResult, ToolParameter

class GreeterTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.add_parameter(ToolParameter(
            name="name",
            type="string",
            description="Person to greet",
            required=True
        ))
    
    @property
    def tool_id(self) -> str:
        return "greeter"
    
    @property
    def name(self) -> str:
        return "Greeter Tool"
        
    @property
    def description(self) -> str:
        return "Greets a person by name."
    
    # execute can be sync or async (asyncio coroutine)
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        if "name" not in params:
            return ToolResult(success=False, error="Missing required parameter: name")
            
        greeting = f"Hello, {params['name']}! Welcome to AXIOM."
        return ToolResult(success=True, output=greeting)

# Register and use
greeter = GreeterTool()
tool_registry.register(greeter)

# Manual invocation (bypassing the agent)
res = greeter(name="Alice")
print(res.output)
```

## 4. Troubleshooting

* **Missing Dependencies?** Run `pip install -e .` again to ensure all required packages (like `aiosqlite` and `psutil`) are installed.
* **Database Locked?** If another instance of AXIOM crashed and held the SQLite lock, you may need to delete `axiom.db`.
* **Out of Memory?** If Ollama freezes, set `export AXIOM_MODEL="llama3:8b"` to force the use of a smaller model before starting AXIOM.
