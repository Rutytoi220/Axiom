import pytest
from axiom.tools import ToolResult, ToolParameter, BaseTool, EchoTool, ShellTool, FileReadTool, FileWriteTool, SystemInfoTool, FileTool
from axiom.tools.os_assist import SafeFileSearchTool, FileOpenerTool, AppLauncherTool
from axiom.tools.document_reader import ReadDocumentContentTool
from axiom.tools.mcp_hub import MCPHub
from axiom.tools.mcp_sse_client import MCPSSEClient
import asyncio
import os

@pytest.mark.asyncio
async def test_tools_coverage():
    tr = ToolResult(True, "out")
    repr(tr)
    tr = ToolResult(False, error="err")
    repr(tr)
    tr.to_dict("tool", {})

    tp = ToolParameter("p", "str", "desc")
    
    class MyTool(BaseTool):
        def execute(self, *args, **kwargs): return ToolResult(True)
        @property
        def tool_id(self): return "my"
        @property
        def name(self): return "my"
        @property
        def description(self): return "my"
    
    mt = MyTool()
    mt.add_parameter(tp)
    mt.schema
    mt.get_info()
    mt.validate_parameters()
    mt.validate_parameters(p="1")
    mt.execute()
    mt(p="1")

    et = EchoTool()
    et.schema
    et.execute({})
    et.execute({"text":"123"})
    
    st = ShellTool(allow_dangerous=True)
    st.schema
    st.add_blocklist_pattern("rm")
    st.remove_blocklist_pattern("rm")
    await st.execute({})
    await st.execute({"command": ""})
    await st.execute({"command": "ls"})

    fr = FileReadTool()
    fr.schema
    await fr.execute({})
    await fr.execute({"operation": "exists", "path": "notfound"})
    await fr.execute({"operation": "exists", "path": "../out"})
    await fr.execute({"operation": "list_dir", "path": "tests"})
    await fr.execute({"operation": "read", "path": "tests/test_tools.py"})
    await fr.execute({"operation": "read", "path": "notfound"})

    fw = FileWriteTool()
    fw.schema
    await fw.execute({})
    await fw.execute({"operation": "write", "path": "test_fw.txt", "content": "1"})
    await fw.execute({"operation": "append", "path": "test_fw.txt", "content": "2"})
    await fw.execute({"operation": "delete", "path": "test_fw.txt"})

    si = SystemInfoTool()
    si.schema
    await si.execute({})
    await si.execute({"metric": "cpu"})

    ft = FileTool()
    ft.schema
    await ft.execute({})
    await ft.execute({"operation": "exists", "path": "test.txt"})

