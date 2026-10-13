"""Unit & Integration tests for Hybrid Fastest Path Tool Router."""

import pytest
import shutil
from unittest.mock import patch, MagicMock

from axiom.core.fast_path_router import FastestPathRouter, FastPathPlan
from instruction_parser import parse as parse_instruction, execute_instruction_fast_path


def test_url_routing():
    """Verify web URLs are intercepted and routed to xdg-open."""
    urls = [
        "https://github.com/ChienGPT/Axiom",
        "http://localhost:8080/dashboard",
        "www.google.com",
    ]
    for url in urls:
        plan = FastestPathRouter.can_route_to_cli("open_browser", {"url": url})
        assert plan is not None, f"Failed to route URL: {url}"
        assert plan.command[0] == "xdg-open"
        assert url in plan.command[1] or ("https://" + url) in plan.command[1]
        assert plan.category == "browser"


def test_app_launch_routing():
    """Verify application launches prioritize CLI binaries or gtk-launch."""
    plan = FastestPathRouter.can_route_to_cli("open_app", {"name": "terminal"})
    assert plan is not None
    assert plan.category == "app"
    cmd0 = plan.command[0]
    assert cmd0.endswith("kitty") or cmd0.endswith("gtk-launch") or cmd0.endswith("terminal")


def test_systemctl_routing():
    """Verify system service management routes to systemctl."""
    plan = FastestPathRouter.can_route_to_cli("service_action", {"command": "restart service bluetooth"})
    if shutil.which("systemctl"):
        assert plan is not None
        assert plan.command == ["systemctl", "restart", "bluetooth"]
        assert plan.category == "service"


def test_audio_routing():
    """Verify audio volume commands route to wpctl."""
    plan = FastestPathRouter.can_route_to_cli("set_volume", {"text": "volume up"})
    if shutil.which("wpctl"):
        assert plan is not None
        assert plan.command[0] == "wpctl"
        assert plan.category == "audio"


def test_gui_fallback_preserved_for_canvas_elements():
    """Verify raw mouse and keyboard clicks on visually locked widgets remain GUI fallback."""
    # A click at coordinates (x, y) with no CLI intent should return None
    plan = FastestPathRouter.can_route_to_cli("mouse_click", {"x": 350, "y": 720, "button": "left"})
    assert plan is None, "Pure mouse_click must NOT be intercepted by CLI router!"

    plan_move = FastestPathRouter.can_route_to_cli("mouse_move", {"x": 100, "y": 200})
    assert plan_move is None, "Pure mouse_move must NOT be intercepted by CLI router!"


def test_instruction_parser_fast_path_integration():
    """Verify instruction_parser tags fast path plans onto parsed LLM instructions."""
    text = "[INSTRUCTION]open_url https://duckduckgo.com[/INSTRUCTION]"
    res = parse_instruction(text)
    assert res.get("type") == "instruction"
    assert res.get("fast_path") is True
    assert res.get("cli_command")[0] == "xdg-open"
    assert "https://duckduckgo.com" in res.get("cli_command")[1]


def test_instruction_parser_pure_gui_fallback():
    """Verify instruction_parser preserves pure GUI instructions without CLI override."""
    text = "[INSTRUCTION]click_mouse 500 300[/INSTRUCTION]"
    res = parse_instruction(text)
    assert res.get("type") == "instruction"
    assert not res.get("fast_path", False)
    assert "cli_command" not in res


@pytest.mark.asyncio
async def test_desktop_automation_tool_fast_path_interception():
    """Verify DesktopAutomationTool delegates fast path actions instead of calling motor controls."""
    from axiom.tools.desktop_control import DesktopAutomationTool

    tool = DesktopAutomationTool()
    # Intercepted action:
    res = await tool.execute("open_url", url="https://example.com")
    assert res.success is True
    assert res.metadata.get("fast_path") is True
    assert res.metadata.get("command") == ["xdg-open", "https://example.com"]
