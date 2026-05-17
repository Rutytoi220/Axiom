# AXIOM - AI Orchestration Framework

A local-first AI orchestration framework built in Python 3.12+.

## Features

- **Event-driven architecture** - All components communicate via event system
- **Modular design** - Clean separation of concerns
- **Plugin system** - Extensible architecture for custom components
- **Local-first** - Runs entirely locally (no external API dependencies)
- **Ollama integration** - Compatible with Ollama for local LLM inference
- **SQLite persistence** - Built-in memory and conversation storage
- **Agent system** - Multi-agent reasoning with event-based communication
- **Tool system** - Extensible tool registry with system command execution
- **CLI interface** - Interactive command-line interface

## Architecture

```
axiom/
├── core/                 # Core engine, events, registry
├── llm/                  # LLM client (Ollama-compatible)
├── memory/               # SQLite persistence layer
├── agents/               # Agent framework and orchestrator
├── tools/                # Tool system and implementations
├── plugins/              # Plugin system with examples
├── api/                  # CLI and API interfaces
├── config.py            # Configuration management
└── main.py              # Main entry point
```

## Requirements

- Python 3.12+
- requests (for HTTP calls to Ollama)
- SQLite3 (included with Python)

## Installation

### From source

```bash
git clone https://github.com/Rutytoi220/Axiom.git
cd axiom
pip install -e .
```

### Development installation

```bash
pip install -e ".[dev]"
```

## Quick Start

### Run the CLI

```bash
python axiom_cli.py
```

Or after installation:

```bash
axiom
```

### Basic commands

```
axiom> ask What can you do?
axiom> tools
axiom> agents
axiom> status
axiom> history
axiom> quit
```

## Architecture Details

### Event System

All inter-component communication happens through the event bus:

```python
from axiom import Engine, Event

engine = Engine()
engine.initialize()

# Subscribe to events
def my_handler(event):
    print(f"Received: {event.event_type}")

engine.event_bus.subscribe("system.initialized", my_handler)
```

### Registry System

Tools, agents, and plugins register themselves dynamically:

```python
from axiom import Engine, ShellCommandTool

engine = Engine()
tool = ShellCommandTool()
engine.registry.register_tool(tool.tool_id, tool)

# Later, retrieve tools
tools = engine.registry.list_tools()
```

### Agents

Agents process input through a reasoning loop:

```python
from axiom import OrchestratorAgent

agent = OrchestratorAgent()
response = agent.process("What is 2+2?")
print(response.output)
```

### Tools

Tools are extensible and can be custom-defined:

```python
from axiom import BaseTool, ToolResult, ToolParameter

class MyTool(BaseTool):
    def __init__(self):
        super().__init__("my_tool", "My Tool", "Does something useful")
        self.add_parameter(ToolParameter("input", "string", "Input text"))
    
    def execute(self, input: str, **kwargs) -> ToolResult:
        result = f"Processed: {input}"
        return ToolResult(success=True, output=result)
```

### Memory

Persistent memory is managed through SQLite:

```python
from axiom import MemoryManager

memory = MemoryManager()
memory.create_conversation("My Chat")
memory.add_message("user", "Hello")
memory.add_message("assistant", "Hi there!")
history = memory.get_conversation_history()
```

### Plugins

Plugins extend AXIOM functionality:

```python
from axiom import NXBTPlugin

plugin = NXBTPlugin()
plugin.initialize()
plugin.enable()
plugin.connect()
plugin.press_button("a")
```

## LLM Integration

AXIOM supports Ollama for local LLM inference:

```bash
# Install and run Ollama
ollama pull neural-chat
ollama serve
```

Then in AXIOM:

```python
from axiom import OllamaClient

llm = OllamaClient()
if llm.is_available():
    response = llm.generate("What is AI?")
    print(response)
```

## Configuration

Configure AXIOM behavior via `AxiomConfig`:

```python
from axiom import AxiomConfig, set_config

config = AxiomConfig(
    debug=True,
    ollama_base_url="http://localhost:11434",
    ollama_model="neural-chat",
    db_path="my_axiom.db"
)
set_config(config)
```

## Development

### Running tests

```bash
pytest
```

### Type checking

```bash
mypy axiom/
```

### Code formatting

```bash
black axiom/
```

### Linting

```bash
flake8 axiom/
```

## System Tools

AXIOM includes built-in tools:

- **shell_command** - Execute shell commands
- **read_file** - Read file contents
- **write_file** - Write to files
- **python_exec** - Execute Python code safely

## Plugins

Built-in plugins:

- **NXBT Plugin** - Nintendo Switch Pro controller emulation
- **Automation Plugin** - Task scheduling and automation

## Directory Structure

After installation, AXIOM creates:

```
~/.axiom/                  # AXIOM home directory
├── axiom.db              # SQLite database
├── logs/                 # Log files
└── plugins/              # Plugin directory
```

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please follow these guidelines:

1. Write tests for new features
2. Use type hints throughout
3. Follow PEP 8 style guide
4. Update documentation

## Troubleshooting

### Ollama not available

Ensure Ollama is running:

```bash
ollama serve
```

### Database errors

Delete the database and restart:

```bash
rm axiom.db
python axiom_cli.py
```

### Import errors

Ensure installation:

```bash
pip install -e .
```

## Roadmap

- [ ] Multi-agent conversation
- [ ] Streaming responses
- [ ] Custom agent types
- [ ] Web API interface
- [ ] Docker containerization
- [ ] Advanced memory management
- [ ] Tool result caching
- [ ] Agent collaboration framework

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

## Acknowledgments

Built with Python 3.12+, inspired by modern AI architectures and local-first philosophy.
