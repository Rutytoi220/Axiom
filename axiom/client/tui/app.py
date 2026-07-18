"""AXIOM Monitor App using Textual."""

import json
import asyncio
import logging
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal

from axiom.client.tui.widgets import (
    TelemetryPanel,
    SwarmDebatePanel,
    FlightRecorderLog,
    TelemetryUpdate,
    SwarmProposalUpdate,
    FlightRecordUpdate
)

logger = logging.getLogger(__name__)


class AxiomMonitorApp(App):
    """The AXIOM System Monitor TUI."""

    CSS_PATH = "monitor.tcss"

    def compose(self) -> ComposeResult:
        yield TelemetryPanel()
        yield SwarmDebatePanel()
        yield FlightRecorderLog()

    async def on_mount(self) -> None:
        """Start the background task to listen to the Unix socket."""
        self.socket_task = asyncio.create_task(self._listen_to_daemon())

    async def _listen_to_daemon(self) -> None:
        """Connect to the AXIOM socket and dispatch events to UI."""
        socket_path = Path.home() / ".axiom" / "axiom.sock"
        
        while True:
            try:
                if not socket_path.exists():
                    self.post_message(FlightRecordUpdate(
                        event_type="SYSTEM",
                        source="Monitor",
                        payload="Connecting... (Waiting for AXIOM Daemon socket)"
                    ))
                    await asyncio.sleep(2)
                    continue

                reader, writer = await asyncio.open_unix_connection(str(socket_path))
                self.post_message(FlightRecordUpdate(
                    event_type="SYSTEM",
                    source="Monitor",
                    payload="Connected to AXIOM Daemon socket."
                ))
                
                # Mock sending some auth/subscription message if necessary
                # writer.write(b'{"jsonrpc": "2.0", "method": "subscribe", "params": {"topics": ["*"]}}\n')
                # await writer.drain()

                while True:
                    line = await reader.readline()
                    if not line:
                        break
                        
                    try:
                        payload = json.loads(line.decode().strip())
                        self._dispatch_payload(payload)
                    except json.JSONDecodeError:
                        continue

            except Exception as e:
                self.post_message(FlightRecordUpdate(
                    event_type="ERROR",
                    source="Monitor",
                    payload=f"Connection error: {e}"
                ))
                await asyncio.sleep(2)

    def _dispatch_payload(self, payload: dict) -> None:
        """Route incoming JSON-RPC payloads to the appropriate UI widgets."""
        if "method" not in payload:
            return
            
        method = payload["method"]
        params = payload.get("params", {})
        
        if method == "event.bus.published":
            event_type = params.get("event_type", "unknown")
            source = params.get("source", "unknown")
            data = params.get("data", {})
            
            # Send everything to flight recorder
            recorder = self.query_one(FlightRecorderLog)
            recorder.post_message(FlightRecordUpdate(
                event_type=event_type,
                source=source,
                payload=str(data)[:200]
            ))
            
            # Specialized routing
            if event_type == "telemetry.update":
                panel = self.query_one(TelemetryPanel)
                panel.post_message(TelemetryUpdate(
                    ram=data.get("ram_percent", 0),
                    vram=data.get("vram_percent", 0),
                    tier=data.get("tier", "tier2")
                ))
            elif event_type == "swarm.proposal":
                panel = self.query_one(SwarmDebatePanel)
                panel.post_message(SwarmProposalUpdate(
                    proposal_id=data.get("proposal_id", "?"),
                    tool=data.get("tool", "?"),
                    status="PROPOSED",
                    agent=data.get("agent", "?")
                ))
            elif event_type == "swarm.vote":
                panel = self.query_one(SwarmDebatePanel)
                panel.post_message(SwarmProposalUpdate(
                    proposal_id=data.get("proposal_id", "?"),
                    tool="vote", # The panel expects a string, maybe we don't have tool here
                    status=data.get("vote", "UNKNOWN"),
                    agent=data.get("voter", "?")
                ))
