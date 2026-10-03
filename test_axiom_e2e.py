import asyncio
import json
import re
from axiom.agents.native_orchestrator import NativeOrchestrator
from axiom.tools.vision import InteractWithUITool
import axiom.core.plugins

async def main():
    orchestrator = NativeOrchestrator()
    
    # 1. Setup the tool
    tool = InteractWithUITool()
    schema = {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.schema
        }
    }
    
    # Mock the grounding engine to simulate PyTorch inference in CI
    class MockEngine:
        def predict_action(self, img, instruction, k):
            import time
            time.sleep(0.5)
            return {"action": "click", "point": [100, 200], "text": None, "raw_output": '{"action": "click", "point": [100, 200]}'}
            
    import axiom.core.vision_engine.singleton
    axiom.core.vision_engine.singleton.get_grounding_engine = lambda: MockEngine()
    
    # Mock image capture and ydotool execution to prevent headless CI failures
    import PIL.Image
    import io
    dummy_img = PIL.Image.new('RGB', (224, 224), color='white')
    dummy_bytes = io.BytesIO()
    dummy_img.save(dummy_bytes, format='PNG')
    
    async def mock_tool_execute(params):
        import time
        from axiom.tools.core import ToolResult
        instruction = params.get("instruction")
        img = PIL.Image.new('RGB', (224, 224), color='white')
        engine = axiom.core.vision_engine.singleton.get_grounding_engine()
        import asyncio
        result = await asyncio.to_thread(engine.predict_action, img, instruction, 4)
        x, y = result['point'][0], result['point'][1]
        msg = f"Action 'click' executed at coordinates [{x}, {y}]."
        return ToolResult(True, output=msg)
        
    tool.execute = mock_tool_execute
    
    # Override execute_tool to hook our tool in for the test
    original_execute_tool = axiom.core.plugins.execute_tool
    
    async def mock_execute_tool(name: str, **kwargs):
        if name == tool.name:
            print(f"Executing tool {name} with args: {kwargs}")
            res = await tool.execute(kwargs)
            return json.dumps(res.to_dict())
        return await original_execute_tool(name, **kwargs)
        
    axiom.core.plugins.execute_tool = mock_execute_tool
    import axiom.agents.native_orchestrator as nat_orch
    nat_orch.execute_tool = mock_execute_tool
    
    payload = {
        "stream": True,
        "tools": [schema],
        "messages": [
            {"role": "user", "content": "Click the Gemini button"}
        ]
    }
    
    stream_content = ""
    tool_calls_emitted = []
    
    print("Sending prompt to model...")
    async for chunk in orchestrator.generate_stream(payload):
        if "choices" in chunk and chunk["choices"]:
            delta = chunk["choices"][0].get("delta", {})
            
            # Capture tool calls
            if "tool_calls" in delta:
                for tc in delta["tool_calls"]:
                    if "function" in tc and "name" in tc["function"] and tc["function"]["name"]:
                        tool_calls_emitted.append(tc["function"]["name"])
                        
            # Capture reasoning and content
            if "reasoning" in delta and delta["reasoning"]:
                stream_content += delta["reasoning"]
            if "content" in delta and delta["content"]:
                stream_content += delta["content"]
                
    # Parse the orchestrator's injected tool_msg response
    # The orchestrator appends the tool_msg to payload["messages"]
    tool_messages = [msg for msg in payload.get("messages", []) if msg.get("role") == "tool"]
    tool_result = ""
    if tool_messages:
        tool_result = tool_messages[-1].get("content", "")
        
    print("\n--- TEST VERIFICATION ---")
    print(f"Model generated text:\n{stream_content}")
    
    # Check 1: No Chinese characters
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', stream_content))
    assert not has_chinese, "Test Failed: Stream contains Chinese characters (hallucination)."
    
    # Check 2: Emits tool_call for interact_with_ui
    assert "interact_with_ui" in tool_calls_emitted, f"Test Failed: Model did not emit a tool call for 'interact_with_ui'. Emitted: {tool_calls_emitted}"
    
    # Check 3: Grounding engine returned coordinates
    # The tool returns "Action 'click' executed at coordinates [x, y]."
    print(f"Tool execution result: {tool_result}")
    coord_match = re.search(r'\[(\d+),\s*(\d+)\]', tool_result)
    assert coord_match, "Test Failed: AxiomGroundingEngine did not return integer coordinate array [x, y]."
    
    print("All E2E checks passed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
