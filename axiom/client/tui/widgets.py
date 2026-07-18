"""TUI Widgets for AXIOM Monitor."""

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, ProgressBar, RichLog, Label
from textual.message import Message


class TelemetryUpdate(Message):
    """Message to update telemetry."""
    def __init__(self, ram: float, vram: float, tier: str):
        self.ram = ram
        self.vram = vram
        self.tier = tier
        super().__init__()


class SwarmProposalUpdate(Message):
    """Message to update swarm debate."""
    def __init__(self, proposal_id: str, tool: str, status: str, agent: str):
        self.proposal_id = proposal_id
        self.tool = tool
        self.status = status
        self.agent = agent
        super().__init__()


class FlightRecordUpdate(Message):
    """Message for new flight log record."""
    def __init__(self, event_type: str, source: str, payload: str):
        self.event_type = event_type
        self.source = source
        self.payload = payload
        super().__init__()


class TelemetryPanel(Static):
    """Displays Hardware RAM/VRAM and active Inference Tier."""

    def compose(self) -> ComposeResult:
        yield Label("Hardware Telemetry", classes="panel-title")
        yield Horizontal(
            Label("RAM:  ", id="ram-lbl"),
            ProgressBar(total=100, show_eta=False, id="ram-bar"),
            classes="telemetry-row"
        )
        yield Horizontal(
            Label("VRAM: ", id="vram-lbl"),
            ProgressBar(total=100, show_eta=False, id="vram-bar"),
            classes="telemetry-row"
        )
        yield Horizontal(
            Label("Active Router Tier: "),
            Label("TIER 2", id="tier-badge", classes="tier-badge")
        )

    def on_telemetry_update(self, message: TelemetryUpdate) -> None:
        """Update gauges when telemetry arrives."""
        ram_bar = self.query_one("#ram-bar", ProgressBar)
        vram_bar = self.query_one("#vram-bar", ProgressBar)
        tier_badge = self.query_one("#tier-badge", Label)
        
        ram_bar.update(progress=message.ram)
        vram_bar.update(progress=message.vram)
        tier_badge.update(f"TIER {message.tier.upper().replace('TIER', '')}")


class SwarmDebatePanel(Static):
    """Displays active sub-agent proposals and voting status."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.proposals = {}  # Keep track of recent proposals
        self.log_widget = None

    def compose(self) -> ComposeResult:
        yield Label("Swarm Consensus Debate", classes="panel-title")
        self.log_widget = RichLog(highlight=True, markup=True)
        yield self.log_widget

    def on_swarm_proposal_update(self, message: SwarmProposalUpdate) -> None:
        if not self.log_widget:
            return
            
        color = "white"
        if message.status == "APPROVED":
            color = "green"
        elif message.status == "REJECTED":
            color = "red"
        elif message.status == "PROPOSED":
            color = "yellow"
            
        text = f"[[{color}]{message.status}[/]] {message.agent} -> {message.tool} (ID: {message.proposal_id[:8]})"
        self.log_widget.write(text)


class FlightRecorderLog(Static):
    """Displays a live streaming log of EventBus bus.published events."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.log_widget = None

    def compose(self) -> ComposeResult:
        yield Label("Live EventBus Flight Recorder", classes="panel-title")
        self.log_widget = RichLog(highlight=True, markup=True, wrap=True)
        yield self.log_widget

    def on_flight_record_update(self, message: FlightRecordUpdate) -> None:
        if not self.log_widget:
            return
            
        text = f"[bold cyan]{message.event_type}[/] [dim]from {message.source}[/]\n  {message.payload}"
        self.log_widget.write(text)
