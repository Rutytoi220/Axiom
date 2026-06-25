"""AXIOM Command-line interface."""

import click
from axiom.events import EventBus
from axiom.registry import Registry
from axiom.tools import EchoTool
from axiom.engine import Engine
from axiom.memory import SyncMemoryStore as MemoryStore
from axiom.llm import OllamaClient, OllamaError

_bus = EventBus()
_registry = Registry()
_memory = MemoryStore(":memory:")
_engine = Engine(bus=_bus, registry=_registry, memory=_memory)
_registry.register("echo", EchoTool())


@click.group()
def cli():
    """AXIOM - Simple AI Orchestration Framework"""
    pass


@cli.command("status")
def status():
    """Show engine status."""
    status_info = _engine.status()
    click.echo(f"Engine running: {status_info['running']}")
    click.echo(f"Started at: {status_info['started_at']}")
    click.echo(f"Events logged: {status_info['event_count']}")


@cli.command("start")
def start():
    """Start the engine."""
    _engine.start()
    click.echo("Engine started")


@cli.command("stop")
def stop():
    """Stop the engine."""
    _engine.stop()
    click.echo("Engine stopped")


@cli.command("event-test")
def event_test():
    """Publish a test event and print the event log."""
    received = []
    _bus.subscribe("test.ping", lambda n, d: received.append((n, d)))
    _bus.publish_sync("test.ping", {"message": "hello from AXIOM"})
    log = _bus.log()
    click.echo(f"Event log ({len(log)} entries):")
    for entry in log:
        click.echo(f"  [{entry['event']}] {entry['data']}")
    click.echo(f"Handler received: {len(received)} event(s)")


@cli.command("llm-status")
def llm_status():
    """Show Ollama connection status and available models."""
    client = OllamaClient()
    if client.is_available():
        click.echo("Ollama: ONLINE")
        models = client.list_models()
        if models:
            click.echo("Available models:")
            for m in models:
                click.echo(f"  - {m}")
        else:
            click.echo("No models found.")
    else:
        click.echo("Ollama: OFFLINE (is Ollama running?)")


@cli.command("llm-ask")
@click.argument("prompt")
def llm_ask(prompt):
    """Send a prompt to Ollama and print the response."""
    client = OllamaClient()
    if not client.is_available():
        click.echo("Error: Ollama is offline. Start Ollama first.")
        raise SystemExit(1)
    try:
        response = client.generate(prompt)
        click.echo(response)
    except OllamaError as e:
        click.echo(f"Error: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
