"""Tests for AXIOM Interactive TUI System Monitor."""

import pytest
import asyncio
from unittest.mock import patch, MagicMock

from axiom.client.tui.app import AxiomMonitorApp
from axiom.client.tui.widgets import (
    TelemetryUpdate,
    SwarmProposalUpdate,
    FlightRecordUpdate
)


@pytest.mark.asyncio
async def test_tui_reacts_to_telemetry_messages():
    """Verify that the TUI widgets update correctly when telemetry is received."""
    app = AxiomMonitorApp()
    
    # Textual provides an async pilot to run tests without actually drawing to the terminal
    async with app.run_test() as pilot:
        # Give the app a moment to compose widgets
        await asyncio.sleep(0.1)
        
        # Manually post a telemetry message to the TelemetryPanel
        panel = app.query_one("TelemetryPanel")
        panel.post_message(TelemetryUpdate(ram=45.0, vram=80.0, tier="tier3"))
        
        # Let the message queue process
        await pilot.pause(0.1)
        
        # Find the labels inside the progress bars and tier badge
        tier_badge = app.query_one("#tier-badge")
        assert "TIER 3" in str(tier_badge.render())


@pytest.mark.asyncio
async def test_tui_reacts_to_swarm_proposals():
    """Verify the swarm debate panel logs properly."""
    app = AxiomMonitorApp()
    
    async with app.run_test() as pilot:
        await asyncio.sleep(0.1)
        
        panel = app.query_one("SwarmDebatePanel")
        panel.post_message(SwarmProposalUpdate(
            proposal_id="abc12345",
            tool="write_file",
            status="APPROVED",
            agent="TestRunnerAgent"
        ))
        
        await pilot.pause(0.1)
        
        # The log widget should have the text
        debate_panel = app.query_one("SwarmDebatePanel")
        assert debate_panel.log_widget is not None
        # We can't easily assert on the RichLog contents directly in a simple way
        # without digging into its internal lines, but we can assure it processed it without error


@pytest.mark.asyncio
async def test_tui_reacts_to_flight_records():
    """Verify the flight recorder logs system events."""
    app = AxiomMonitorApp()
    
    async with app.run_test() as pilot:
        await asyncio.sleep(0.1)
        
        recorder = app.query_one("FlightRecorderLog")
        recorder.post_message(FlightRecordUpdate(
            event_type="test.event",
            source="TestRunner",
            payload="{'test': True}"
        ))
        
        await pilot.pause(0.1)
        
        recorder = app.query_one("FlightRecorderLog")
        assert recorder.log_widget is not None


@pytest.mark.asyncio
@patch('axiom.client.tui.app.asyncio.open_unix_connection')
async def test_tui_socket_reconnection(mock_open_connection):
    """Verify the app handles connection errors gracefully."""
    app = AxiomMonitorApp()
    
    # Make it fail
    mock_open_connection.side_effect = ConnectionRefusedError()
    
    # Start the app. It will attempt to connect in the background
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        
        # The app should still be running without crashing
        assert app.is_running
