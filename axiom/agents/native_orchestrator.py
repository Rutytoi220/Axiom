import json
import httpx
from typing import AsyncGenerator
from axiom.core.plugins import get_tool_schemas, execute_tool

class NativeOrchestrator:
    async def generate_stream(self, payload: dict, depth: int = 0) -> AsyncGenerator[dict, None]:
        if depth > 10:
            yield {"choices": [{"delta": {"content": "\n[Error: Exceeded max tool execution depth]"}}]}
            return

        if depth == 0:
            system_prompt = {
                "role": "system",
                "content": (
                    "You are AXIOM, a local-first AI orchestrator. "
                    "CRITICAL DIRECTIVE: You have access to dedicated API tools (e.g., fetch_weather) and raw shell/system tools (e.g., shell_exec, ssh, distrobox). "
                    "You MUST ALWAYS prefer dedicated API tools. DO NOT attempt to use shell_exec, SSH, or Distrobox to run commands (like curl or python scripts) if a dedicated tool exists for the task. "
                    "Never guess tool parameters. If a tool fails, explain the error; do not aggressively retry shell commands. "
                    "CRITICAL RULE: NEVER use the ask_human tool to ask the user for screen coordinates, visual layouts, or UI element locations. To interact with the screen, call the `interact_with_ui` tool and provide a precise text instruction of what you want to click or type. The dedicated vision subsystem will handle the spatial coordinates."
                )
            }
            
            if not payload.get("messages") or payload["messages"][0].get("role") != "system":
                payload.setdefault("messages", []).insert(0, system_prompt)
            else:
                payload["messages"][0]["content"] += f"\n\n{system_prompt['content']}"


        from axiom.config import get_config
        payload["model"] = get_config().ollama_model

        timeout_config = httpx.Timeout(connect=10.0, read=300.0, write=20.0, pool=20.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            async with client.stream(
                "POST",
                "http://127.0.0.1:11434/v1/chat/completions",
                json=payload
            ) as resp:
                if resp.status_code != 200:
                    await resp.aread()
                    yield {"choices": [{"delta": {"content": f"\n⚠️ [API Error] HTTP {resp.status_code}: {resp.text}\n"}}]}
                    return

                pending_tool_calls = []
                is_reasoning = False
                collected_assistant_text = []

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            
                            if "reasoning_content" in delta:
                                r_content = delta.pop("reasoning_content")
                                if not is_reasoning:
                                    delta["content"] = "<think>" + r_content
                                    is_reasoning = True
                                else:
                                    delta["content"] = r_content
                                    
                            if "content" in delta and is_reasoning and not "reasoning_content" in data.get("choices", [{}])[0].get("delta", {}):
                                delta["content"] = "</think>" + delta["content"]
                                is_reasoning = False

                            if "content" in delta and delta["content"]:
                                collected_assistant_text.append(delta["content"])

                            if "tool_calls" in delta:
                                for tc in delta["tool_calls"]:
                                    idx = tc["index"]
                                    while len(pending_tool_calls) <= idx:
                                        pending_tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                                    if "id" in tc and tc["id"]:
                                        pending_tool_calls[idx]["id"] = tc["id"]
                                    if "function" in tc:
                                        if "name" in tc["function"] and tc["function"]["name"]:
                                            pending_tool_calls[idx]["function"]["name"] = tc["function"]["name"]
                                        if "arguments" in tc["function"] and tc["function"]["arguments"]:
                                            pending_tool_calls[idx]["function"]["arguments"] += tc["function"]["arguments"]

                            yield data
                        except json.JSONDecodeError:
                            pass

        if pending_tool_calls:
            assistant_msg = {
                "role": "assistant",
                "content": "".join(collected_assistant_text) if collected_assistant_text else None,
                "tool_calls": pending_tool_calls
            }
            payload["messages"].append(assistant_msg)

            for tc in pending_tool_calls:
                func_name = tc["function"]["name"]
                func_args_str = tc["function"]["arguments"]
                tool_call_id = tc["id"]

                try:
                    func_args = json.loads(func_args_str) if func_args_str else {}
                except Exception:
                    func_args = {}

                try:
                    tool_result = await execute_tool(func_name, **func_args)
                    
                    if not isinstance(tool_result, str):
                        tool_result = json.dumps(tool_result, indent=2)
                    res_str = tool_result
                except Exception as e:
                    res_str = json.dumps({"error": str(e), "status": "tool_execution_failed"})

                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": func_name,
                    "content": res_str
                }
                payload["messages"].append(tool_msg)

            async for chunk in self.generate_stream(payload, depth=depth + 1):
                yield chunk
