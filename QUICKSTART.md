# AXIOM Quick Start Guide

Get up and running with AXIOM in 5 minutes.

## 1. Installation

```bash
cd /path/to/axiom
pip install -e .
```

Or run directly:

```bash
python axiom_cli.py
```

## 2. Start the CLI

```bash
axiom
```

You'll see the welcome screen:

```
╔═══════════════════════════════════════════════════════════════╗
║                    AXIOM - AI Orchestration                   ║
║              Local-First LLM Framework for Linux              ║
║                    Type 'help' for commands                   ║
╚═══════════════════════════════════════════════════════════════╝

axiom>
```

## 3. Basic Commands

### Ask a Question

```
axiom> ask What can you do?
```

### View System Status

```
axiom> status
```

This shows:
- Engine status
- LLM availability (Ollama)
- Memory/database info
- Registered tools, agents, plugins

### List Tools

```
axiom> tools
```

Shows all registered tools with their parameters and execution count.

### List Agents

```
axiom> agents
```

Shows all registered agents and their state.

### List Plugins

```
axiom> plugins
```

Shows all loaded plugins and their status.

### View Conversation History

```
axiom> history
```

Displays the current conversation.

### Clear History

```
axiom> clear_history
```

Starts a fresh conversation.

### Exit

```
axiom> quit
```

## 4. First Script

Create `my_axiom_script.py`:

```python
from axiom import Engine, OrchestratorAgent, MemoryManager

# Initialize
engine = Engine()
engine.initialize()

agent = OrchestratorAgent()
agent.set_engine_refs(engine.event_bus, engine.registry)

memory = MemoryManager()
memory.create_conversation("My Session")

# Ask a question
response = agent("What is the meaning of life?")

# Store in memory
memory.add_message("user", "What is the meaning of life?")
memory.add_message("assistant", response.output or "")

print(response.output)

engine.shutdown()
```

Run it:

```bash
python my_axiom_script.py
```

## 5. Using Tools

### Execute Shell Commands

```python
from axiom import ShellCommandTool

tool = ShellCommandTool()
result = tool(command="ls -la")

print(result.output["stdout"])
```

### Read Files

```python
from axiom import ReadFileTool

tool = ReadFileTool()
result = tool(path="/path/to/file.txt")

if result.success:
    print(result.output["content"])
```

### Write Files

```python
from axiom import WriteFileTool

tool = WriteFileTool()
result = tool(path="output.txt", content="Hello World")

print(f"Wrote {result.output['size']} bytes")
```

### Execute Python Code

```python
from axiom import PythonExecTool

tool = PythonExecTool()
result = tool(code="print('2 + 2 =', 2+2)")

print(result.output["stdout"])
```

## 6. LLM Integration (Optional)

If you have Ollama installed and running:

```bash
# Install Ollama
# Download from https://ollama.ai

# Run Ollama
ollama serve

# In another terminal, pull a model
ollama pull neural-chat
```

Then in AXIOM:

```python
from axiom import OllamaClient

llm = OllamaClient()

if llm.is_available():
    response = llm.generate("What is machine learning?")
    print(response)
else:
    print("Ollama not available")
```

## 7. Creating Your First Tool

Create `my_tools.py`:

```python
from axiom import BaseTool, ToolResult, ToolParameter


class GreeterTool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_id="greeter",
            name="Greeter",
            description="Greets a person"
        )
        self.add_parameter(ToolParameter(
            name="name",
            type="string",
            description="Person to greet",
            required=True
        ))
    
    def execute(self, name: str, **kwargs) -> ToolResult:
        greeting = f"Hello, {name}! Welcome to AXIOM."
        return ToolResult(success=True, output=greeting)
```

Use it:

```python
from axiom import Engine
from my_tools import GreeterTool

engine = Engine()
engine.initialize()

greeter = GreeterTool()
engine.registry.register_tool(greeter.tool_id, greeter)

result = greeter(name="Alice")
print(result.output)
```

## 8. Creating Your First Agent

Create `my_agents.py`:

```python
from axiom import BaseAgent, AgentResponse
from typing import Optional, Dict


class CalculatorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="calculator",
            name="Calculator Agent",
            description="Solves math problems"
        )
    
    def process(self, input_text: str, context: Optional[Dict] = None) -> AgentResponse:
        try:
            result = eval(input_text)
            return AgentResponse(
                agent_id=self.agent_id,
                success=True,
                output=f"Result: {result}"
            )
        except Exception as e:
            return AgentResponse(
                agent_id=self.agent_id,
                success=False,
                output=None,
                error=str(e)
            )
```

Use it:

```python
from axiom import Engine
from my_agents import CalculatorAgent

engine = Engine()
engine.initialize()

agent = CalculatorAgent()
agent.set_engine_refs(engine.event_bus, engine.registry)

response = agent("2 + 2 * 3")
print(response.output)
```

## 9. Configuration

Create `axiom_config.py`:

```python
from axiom import AxiomConfig, set_config

config = AxiomConfig(
    debug=True,
    log_level="DEBUG",
    ollama_model="mistral",
    ollama_temperature=0.5,
    db_path="my_axiom.db"
)

set_config(config)

# Now use AXIOM with custom config
from axiom import Engine

engine = Engine()
engine.initialize()
```

## 10. Common Patterns

### Pattern: Tool Orchestration

```python
from axiom import Engine, ShellCommandTool, ReadFileTool

engine = Engine()
engine.initialize()

# Register tools
shell = ShellCommandTool()
reader = ReadFileTool()

engine.registry.register_tool(shell.tool_id, shell)
engine.registry.register_tool(reader.tool_id, reader)

# Use tools
result1 = shell(command="find . -name '*.txt'")
file_path = result1.output["stdout"].strip().split('\n')[0]

result2 = reader(path=file_path)
print(f"Contents of {file_path}:")
print(result2.output["content"])
```

### Pattern: Multi-Step Processing

```python
from axiom import Engine, MemoryManager, OrchestratorAgent

engine = Engine()
engine.initialize()

memory = MemoryManager()
memory.create_conversation("Multi-Step")

agent = OrchestratorAgent()
agent.set_engine_refs(engine.event_bus, engine.registry)

# Step 1
q1 = "Analyze the first part"
r1 = agent(q1)
memory.add_message("user", q1)
memory.add_message("assistant", r1.output)

# Step 2
q2 = "Based on that, what about the second part?"
r2 = agent(q2)
memory.add_message("user", q2)
memory.add_message("assistant", r2.output)

# Review
history = memory.get_conversation_history()
```

### Pattern: Event-Driven Processing

```python
from axiom import Engine, Event

engine = Engine()
engine.initialize()

# Define handlers
def on_error(event: Event):
    print(f"ERROR: {event.data['error']}")

def on_completion(event: Event):
    print(f"DONE: {event.data.get('result')}")

# Subscribe
engine.event_bus.subscribe("error.handler", on_error)
engine.event_bus.subscribe("task.complete", on_completion)

# Publish events
success_event = Event(
    event_type="task.complete",
    source="MyScript",
    data={"result": "Operation succeeded"}
)

engine.event_bus.publish(success_event)
```

## Troubleshooting

### ImportError: No module named 'axiom'

```bash
# Install from source
pip install -e .
```

### Database locked error

```bash
# Remove and recreate database
rm axiom.db
python axiom_cli.py
```

### "Ollama not available"

```bash
# Start Ollama in another terminal
ollama serve

# Pull a model
ollama pull neural-chat
```

### Agent not responding

```python
# Check if agent is registered
agents = engine.registry.list_agents()
print(agents)

# Check agent state
agent_info = agent.get_info()
print(f"State: {agent_info['state']}")
```

## Next Steps

1. Read the full README.md
2. Check DEVELOPER_GUIDE.md for advanced topics
3. Run the example scripts:
   - `python example_library.py`
   - `python example_custom_tool.py`
   - `python example_custom_agent.py`
4. Create your own tools and agents
5. Integrate with Ollama for LLM capabilities
6. Join the community and contribute!

## Getting Help

- Check existing documentation
- Review example scripts
- Look at the source code (well-commented)
- Open an issue on GitHub

Happy coding with AXIOM! 🚀
