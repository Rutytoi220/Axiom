import asyncio
import json
import re
from axiom.agents.native_orchestrator import NativeOrchestrator
from axiom.tools.vision import InteractWithUITool
import axiom.core.plugins

async def main():
    orchestrator = NativeOrchestrator()
    
    # 1. Verify the tool registry is purged of legacy tools and contains interact_with_ui
    from axiom.core.plugins import get_tool_schemas, load_plugins
    load_plugins()
    dynamic_tools = get_tool_schemas(0)
    tool_names = [s["function"]["name"] for s in dynamic_tools]
    print(f"Loaded dynamic tools: {tool_names}")
    
    assert "capture_desktop_vision" not in tool_names, "CRITICAL: Legacy tool capture_desktop_vision found in tool registry!"
    assert "ydotool_click" not in tool_names, "CRITICAL: Legacy tool ydotool_click found in tool registry!"
    assert "ydotool_type" not in tool_names, "CRITICAL: Legacy tool ydotool_type found in tool registry!"
    assert "wayland_input" not in tool_names, "CRITICAL: Legacy tool wayland_input found in tool registry!"
    assert "interact_with_ui" in tool_names, "CRITICAL: interact_with_ui tool is missing from tool registry!"
    print("✓ Tool registry verified: Zero legacy vision/input tools present, interact_with_ui active.")

    # Import and pre-warm resident AxiomGroundingEngine into CUDA memory
    from axiom.core.vision_engine.axiom_engine import AxiomGroundingEngine
    from axiom.core.vision_engine.singleton import get_grounding_engine

    # Free any active Ollama models from VRAM so the resident grounding engine can load cleanly
    import httpx
    try:
        from axiom.config import get_config
        cfg = get_config()
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{cfg.ollama_base_url}/api/generate",
                json={"model": cfg.ollama_model, "keep_alive": 0}
            )
    except Exception:
        pass

    print("Pre-warming resident AxiomGroundingEngine into CUDA memory...")
    get_grounding_engine()

    # Wire execute_tool directly to the dynamic plugin system with logging
    original_execute_tool = axiom.core.plugins.execute_tool
    
    async def live_execute_tool(name: str, **kwargs):
        if name == "interact_with_ui":
            print(f"\n[LIVE EXECUTION] Executing live tool '{name}' via plugin registry with args: {kwargs}")
            res = await original_execute_tool(name, **kwargs)
            print(f"[LIVE EXECUTION] Live tool execution returned: {res}")
            return res
        return await original_execute_tool(name, **kwargs)
        
    axiom.core.plugins.execute_tool = live_execute_tool
    import axiom.agents.native_orchestrator as nat_orch
    nat_orch.execute_tool = live_execute_tool
    
    payload = {
        "stream": True,
        "tools": dynamic_tools,
        "messages": [
            {"role": "user", "content": "I have two Gemini windows open. Can you click the '+' button on the left Gemini window for me?"}
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
    
    # Check 4: Strict assertion that final parsed output string contains absolutely no <function> or <highlight> tags
    from axiom.cli.tui import strip_xml_tags
    final_parsed_output = strip_xml_tags(stream_content)
    assert not re.search(r'</?(?:function|highlight)', final_parsed_output, re.IGNORECASE), \
        f"Test Failed: Final parsed output string contains <function> or <highlight> tags: {final_parsed_output}"

    # Verify tag purger against raw XML leak samples (preserving inner conversational response)
    synthetic_sample = "<function name=\"click_ui\">Click</function> the <highlight id=\"gemini_btn\">Gemini button</highlight>."
    purged_sample = strip_xml_tags(synthetic_sample)
    assert not re.search(r'</?(?:function|highlight)', purged_sample, re.IGNORECASE), \
        f"Test Failed: XML tag purger failed to remove tags from synthetic sample: {purged_sample}"
    assert "Click the Gemini button." == purged_sample.strip(), \
        f"Test Failed: Inner text was corrupted during XML tag purge: {purged_sample}"
    print("✓ Check 4: Final parsed output contains zero <function> or <highlight> tags, and tag purger verified.")

    print("All E2E checks passed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
