import pytest
import json
from unittest.mock import patch, MagicMock
from axiom.tools.mcp_hub import MCPHub

class MockRegistry:
    def __init__(self):
        self.tools = {}
    def register_tool(self, name, tool):
        self.tools[name] = tool

@patch("axiom.tools.mcp_hub.subprocess.Popen")
def test_mcp_register_tool(mock_popen, tmp_path):
    mock_process = MagicMock()
    mock_popen.return_value = mock_process
    
    # Mock the stdout readline to return the init response, then the tool list
    # The MCPHub expects:
    # 1. read init response
    # 2. read tools/list response
    mock_process.stdout.readline.side_effect = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}),
        json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "tools": [{
                    "name": "test_mcp_tool",
                    "description": "A test tool",
                    "inputSchema": {
                        "properties": {"arg1": {"type": "string"}},
                        "required": ["arg1"]
                    }
                }]
            }
        }),
        "" # end of stream
    ]

    registry = MockRegistry()
    hub = MCPHub(registry)
    
    # Manually trigger connection to avoid writing to actual ~/.axiom
    with patch.object(hub, 'config_path', tmp_path / "mcp_services.json"):
        hub._ensure_config()
        hub.add_server("test_server", "echo", ["hello"])
        
    assert "test_server_test_mcp_tool" in registry.tools
    tool = registry.tools["test_server_test_mcp_tool"]
    
    info = tool.get_info()
    assert info["name"] == "test_server_test_mcp_tool"
    assert info["parameters"][0]["name"] == "arg1"
    assert info["parameters"][0]["required"] is True

@patch("axiom.tools.mcp_hub.subprocess.Popen")
def test_mcp_tool_execution(mock_popen, tmp_path):
    mock_process = MagicMock()
    mock_popen.return_value = mock_process
    
    mock_process.stdout.readline.side_effect = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}),
        json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "tools": [{
                    "name": "test_tool",
                    "description": "tool desc"
                }]
            }
        }),
        # Tool call response
        json.dumps({
            "jsonrpc": "2.0",
            "id": 999,
            "result": {
                "content": [{"type": "text", "text": "tool output success"}]
            }
        }),
        ""
    ]

    registry = MockRegistry()
    hub = MCPHub(registry)
    with patch.object(hub, 'config_path', tmp_path / "mcp_services.json"):
        hub._ensure_config()
        hub.add_server("test_server", "echo", ["hello"])
        
    tool = registry.tools["test_server_test_tool"]
    res = tool.execute(arg1="value")
    
    assert res["success"] is True
    assert res["output"] == "tool output success"
