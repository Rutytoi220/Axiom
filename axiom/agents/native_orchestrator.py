import json
import re
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
                    "You are AXIOM, a local-first AI orchestrator with a strict Three-Tier Automation Hierarchy.\n\n"
                    "THREE-TIER AUTOMATION DIRECTIVES:\n"
                    "1. TIER 1 (System IPC - hyprctl): For managing windows, switching workspaces, focusing applications, "
                    "querying window geometry, or window state, ALWAYS use the 'manage_desktop_window' tool. "
                    "NEVER simulate mouse clicks or visual coordinates for window/workspace management.\n"
                    "2. TIER 2 (Semantic UI - Chrome DevTools Protocol): For interacting with web browsers (Zen Browser, "
                    "Chrome, Brave, Chromium) or web applications (e.g. Monkeytype, Gemini web, YouTube, web forms) and "
                    "Electron apps, ALWAYS use the 'interact_with_browser' tool. It executes sub-10ms deterministic "
                    "clicks, typing, and JS evaluations via DOM selectors.\n"
                    "3. TIER 3 (Vision Fallback - Grounding Engine): If and ONLY if the target application has NO DOM or IPC "
                    "interface (e.g., native non-accessible binaries, games, raw canvas, or legacy applications), use the "
                    "'interact_with_ui' tool. It captures a screen buffer and calculates spatial coordinates.\n\n"
                    "GENERAL DIRECTIVES:\n"
                    "- ALWAYS prefer dedicated API tools over raw shell commands. DO NOT attempt to use shell_exec, SSH, or Distrobox "
                    "if a dedicated tool exists for the task.\n"
                    "- Never guess tool parameters. If a tool fails, explain the error; do not aggressively retry shell commands.\n"
                    "- CRITICAL RULE: NEVER use the ask_human tool to ask the user for screen coordinates or UI element locations."
                )
            }
            
            if not payload.get("messages") or payload["messages"][0].get("role") != "system":
                payload.setdefault("messages", []).insert(0, system_prompt)
            else:
                payload["messages"][0]["content"] += f"\n\n{system_prompt['content']}"

        if not payload.get("tools"):
            payload["tools"] = get_tool_schemas(0)

        from axiom.config import get_config
        config = get_config()
        payload["model"] = config.ollama_model
        base_url = getattr(config, "ollama_base_url", "http://127.0.0.1:11434").rstrip("/")

        # Scrub images from payload to prevent context-window collapse
        for msg in payload.get("messages", []):
            if "images" in msg:
                del msg["images"]
            if isinstance(msg.get("content"), list):
                # Filter out image_url items
                text_parts = [c.get("text", "") for c in msg["content"] if c.get("type") == "text"]
                msg["content"] = "\n".join(text_parts)

        # Enforce Two-Brain VRAM Eviction: Evict vision engine from CUDA memory before text streaming
        try:
            from axiom.core.vision_engine.singleton import evict_grounding_engine
            evict_grounding_engine()
        except Exception:
            pass

        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # Enforce 100% GPU layer offload in Ollama
        payload.setdefault("options", {})["num_gpu"] = 99

        timeout_config = httpx.Timeout(connect=10.0, read=300.0, write=20.0, pool=20.0)
        try:
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/v1/chat/completions",
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
        except httpx.ConnectError as exc:
            yield {"choices": [{"delta": {"content": f"\n⚠️ [Connection Error] Could not connect to local AI engine at {base_url}: {exc}. Ensure Ollama is running.\n"}}]}
            return
        except httpx.RequestError as exc:
            yield {"choices": [{"delta": {"content": f"\n⚠️ [Request Error] Communication failure with {base_url}: {exc}\n"}}]}
            return

        if not pending_tool_calls and collected_assistant_text:
            full_text = "".join(collected_assistant_text).strip()
            candidate = full_text
            if candidate.startswith("```json"):
                candidate = candidate[7:]
            elif candidate.startswith("```"):
                candidate = candidate[3:]
            if candidate.endswith("```"):
                candidate = candidate[:-3]
            candidate = candidate.strip()

            known_tools = set()
            if payload.get("tools"):
                for t in payload["tools"]:
                    if isinstance(t, dict) and "function" in t and "name" in t["function"]:
                        known_tools.add(t["function"]["name"])

            parsed_candidates = []
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict) and "name" in parsed:
                    if not known_tools or parsed["name"] in known_tools:
                        parsed_candidates.append(parsed)
                elif isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and "name" in item:
                            if not known_tools or item["name"] in known_tools:
                                parsed_candidates.append(item)
            except Exception:
                pass

            if not parsed_candidates:
                match = re.search(r'\{[\s\S]*"name"\s*:\s*"([^"]+)"[\s\S]*\}', candidate)
                if match:
                    try:
                        extracted = json.loads(match.group(0).rstrip('`').strip())
                        if isinstance(extracted, dict) and "name" in extracted:
                            if not known_tools or extracted["name"] in known_tools:
                                parsed_candidates.append(extracted)
                    except Exception:
                        pass

            for idx, candidate_dict in enumerate(parsed_candidates):
                func_name = candidate_dict.get("name")
                func_args = candidate_dict.get("arguments", candidate_dict.get("parameters", {}))
                func_args_str = json.dumps(func_args) if isinstance(func_args, dict) else str(func_args)
                call_id = f"call_native_{idx}"
                pending_tool_calls.append({
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": func_name,
                        "arguments": func_args_str
                    }
                })
                yield {
                    "choices": [{
                        "delta": {
                            "tool_calls": [{
                                "index": idx,
                                "id": call_id,
                                "type": "function",
                                "function": {
                                    "name": func_name,
                                    "arguments": func_args_str
                                }
                            }]
                        }
                    }]
                }

            if parsed_candidates:
                collected_assistant_text = []

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

    @staticmethod
    def route_tier(task_description: str) -> str:
        """Determines the automation tier based on task description.

        Returns:
            'tier1_ipc': For window/workspace management -> manage_desktop_window
            'tier2_browser': For browser/web/DOM interaction -> interact_with_browser
            'tier3_vision': Fallback for non-accessible canvas/games -> interact_with_ui
        """
        task_lower = task_description.lower().strip()

        # Tier 3 explicit overrides (no DOM, canvas, game, pixel, screen coordinates, legacy)
        tier3_overrides = [
            r"\b(no dom|without dom|non-accessible|canvas|opengl|vulkan|game|spaceship|pixel|coordinates|legacy binary)\b",
            r"\b(grounding|vision engine|screenshot)\b",
        ]
        for pattern in tier3_overrides:
            if re.search(pattern, task_lower):
                return "tier3_vision"

        # Tier 1 indicators (Window management & Hyprland IPC)
        tier1_patterns = [
            r"\b(window|windows|workspace|workspaces|fullscreen|floating|tile|tiling)\b",
            r"\b(focus|switch to|move to|close)\s+(window|workspace)\b",
            r"\b(active window|list windows|hyprctl|hyprland)\b",
        ]
        for pattern in tier1_patterns:
            if re.search(pattern, task_lower):
                return "tier1_ipc"

        # Tier 2 indicators (Web browser, DOM, CDP, web apps)
        tier2_patterns = [
            r"\b(browser|chrome|chromium|brave|zen|firefox|monkeytype|gemini|youtube|electron)\b",
            r"\b(dom|html|css selector|website|webpage|web page|web app|tab|url|href)\b",
            r"\b(inspect|evaluate|javascript|js)\b",
        ]
        for pattern in tier2_patterns:
            if re.search(pattern, task_lower):
                return "tier2_browser"

        # Tier 3 (Vision fallback)
        return "tier3_vision"

    @classmethod
    def get_tier_tool(cls, task_description: str) -> str:
        """Returns the primary tool name corresponding to the routed tier."""
        tier = cls.route_tier(task_description)
        tier_map = {
            "tier1_ipc": "manage_desktop_window",
            "tier2_browser": "interact_with_browser",
            "tier3_vision": "interact_with_ui",
        }
        return tier_map.get(tier, "interact_with_ui")

