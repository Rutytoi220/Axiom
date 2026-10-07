import asyncio
import json
import re
import shutil
import httpx
from typing import Any, AsyncGenerator, Optional
from axiom.core.plugins import get_tool_schemas, execute_tool, get_tier_timeout

REFUSAL_PHRASES = [
    "cannot see your screen",
    "can't see your screen",
    "as an ai",
    "don't have eyes",
    "cannot interact with your computer",
]

class NativeOrchestrator:
    def __init__(self, max_context_tokens: int = 32768):
        self.max_context_tokens = max_context_tokens
        self._execute_tool = None

    @property
    def execute_tool(self):
        return self._execute_tool or execute_tool

    @execute_tool.setter
    def execute_tool(self, val):
        self._execute_tool = val

    @classmethod
    def is_refusal(cls, text: str) -> bool:
        """Checks if text contains signature conversational refusal phrases."""
        if not text:
            return False
        t_lower = text.lower()
        return any(phrase in t_lower for phrase in REFUSAL_PHRASES)

    @classmethod
    def is_interface_action_query(cls, text: str) -> bool:
        """Determines if a query targets an OS, browser, or interface action."""
        if not text:
            return False
        t_lower = text.lower()
        patterns = [
            r"\b(click|press|tap|double-click|right-click)\b",
            r"\b(open|launch|start|run|close|switch|focus)\b",
            r"\b(window|windows|workspace|workspaces|desktop|screen|display|monitor)\b",
            r"\b(browser|webpage|website|url|tab|button|icon|link|menu)\b",
            r"\b(inspect|navigate|scroll|type|look at|see|find|show me|view)\b",
        ]
        return any(re.search(pat, t_lower) for pat in patterns)

    @staticmethod
    async def get_active_window_context() -> Optional[str]:
        """Query hyprctl activewindow -j non-blockingly and format telemetry header."""
        if not shutil.which("hyprctl"):
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                "hyprctl", "activewindow", "-j",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=1.0)
            if proc.returncode == 0 and stdout:
                data = json.loads(stdout.decode())
                title = data.get("title", "")
                w_class = data.get("class", "")
                workspace = data.get("workspace", {})
                w_id = workspace.get("id", "") if isinstance(workspace, dict) else workspace
                if title or w_class:
                    return f'[Active Window: title="{title}", class="{w_class}", workspace={w_id}]'
        except Exception:
            pass
        return None

    def _build_system_prompt(self, base_directives: Optional[str] = None) -> str:
        """Compile hierarchical system directives, global user instructions, and local project rules."""
        from axiom.core.instructions import InstructionManager
        manager = InstructionManager()
        return manager.get_compiled_instructions(base_directives=base_directives)

    @staticmethod
    def count_tokens(text: str) -> int:
        """Estimate token count for a text string."""
        if not text:
            return 0
        words = len(text.split())
        return max(len(text) // 4, int(words * 1.3), 1)

    @classmethod
    def count_message_tokens(cls, msg: dict) -> int:
        """Estimate token footprint of a chat completion message."""
        content = msg.get("content", "")
        tokens = 0
        if isinstance(content, str):
            tokens = cls.count_tokens(content)
        elif isinstance(content, list):
            tokens = sum(cls.count_tokens(c.get("text", "")) for c in content if isinstance(c, dict))
        elif isinstance(content, dict):
            tokens = cls.count_tokens(json.dumps(content))
        else:
            tokens = cls.count_tokens(str(content))

        if "tool_calls" in msg:
            tokens += cls.count_tokens(json.dumps(msg["tool_calls"]))
        return tokens + 4

    def prune_messages(
        self,
        messages: list[dict],
        max_context_tokens: Optional[int] = None,
        reserve_tokens: int = 1000,
    ) -> list[dict]:
        """Sliding window context budgeting: keeps system directives, initial turn,
        and latest turns within (max_context_tokens - reserve_tokens).
        """
        max_tokens = max_context_tokens or self.max_context_tokens
        budget = max_tokens - reserve_tokens

        system_messages = [m for m in messages if m.get("role") == "system"]
        conv_messages = [m for m in messages if m.get("role") != "system"]

        if not conv_messages:
            return messages

        total_conv_tokens = sum(self.count_message_tokens(m) for m in conv_messages)
        if total_conv_tokens <= budget:
            return messages

        # Initial turn is conv_messages[0]
        initial_turn = conv_messages[0]
        remaining = conv_messages[1:]

        initial_tokens = self.count_message_tokens(initial_turn)
        avail_budget = max(budget - initial_tokens, 0)

        # Retain as many latest turns as fit within avail_budget
        kept_latest = []
        current_tokens = 0
        for msg in reversed(remaining):
            msg_tokens = self.count_message_tokens(msg)
            if current_tokens + msg_tokens <= avail_budget or not kept_latest:
                kept_latest.insert(0, msg)
                current_tokens += msg_tokens
            else:
                break

        pruned_conv = [initial_turn] + kept_latest
        return system_messages + pruned_conv

    async def fetch_dynamic_context_length(self, model: str, base_url: str) -> Optional[int]:
        """Attempt to read context length dynamically from Ollama /api/show."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.post(f"{base_url}/api/show", json={"name": model})
                if resp.status_code == 200:
                    data = resp.json()
                    model_info = data.get("model_info", {})
                    for k, v in model_info.items():
                        if "context_length" in k and isinstance(v, int):
                            return v
        except Exception:
            pass
    @classmethod
    def extract_first_tool_call(
        cls,
        text: str,
        known_tools: Optional[set] = None,
    ) -> Optional[dict]:
        """Tolerantly extract the first valid JSON/XML tool call from model text.

        Resolves issues with small models (e.g. Qwen-7B) emitting concatenated
        JSON objects, markdown code fences embedded in prose, or reasoning text before tool calls.
        Safely extracts and returns the first valid tool call normalized to dual format:
        {"type": "function", "function": {"name": ..., "arguments": ...}, "name": ..., "arguments": ...}
        """
        if not text:
            return None

        def _format_res(name: Any, args: Any) -> Optional[dict]:
            if not name or not isinstance(name, str):
                return None
            clean_name = name
            if clean_name.startswith("functions."):
                clean_name = clean_name[len("functions."):]
            elif clean_name.startswith("tools."):
                clean_name = clean_name[len("tools."):]
            if known_tools and clean_name not in known_tools:
                return None
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    pass
            if not isinstance(args, dict):
                args = {}
            return {
                "type": "function",
                "function": {
                    "name": clean_name,
                    "arguments": args,
                },
                "name": clean_name,
                "arguments": args,
            }

        # 1. XML <tool_call> tags
        if "<tool_call>" in text:
            from axiom.core.system_prompt import extract_xml_tool_call
            xml_res = extract_xml_tool_call(text)
            if xml_res and "function" in xml_res:
                fn = xml_res["function"]
                res = _format_res(fn.get("name", ""), fn.get("arguments", {}))
                if res:
                    return res

        # 2. Markdown code fences embedded anywhere in the text
        # Handles models placing conversational commentary before ```json ... ``` blocks
        for match in re.finditer(r"```(?:json)?\s*([\{\[].*?[\}\]])\s*```", text, re.DOTALL | re.IGNORECASE):
            block = match.group(1).strip()
            decoder = json.JSONDecoder()
            idx = 0
            while idx < len(block):
                brace_pos = block.find("{", idx)
                bracket_pos = block.find("[", idx)
                if brace_pos != -1 and bracket_pos != -1:
                    start_pos = min(brace_pos, bracket_pos)
                elif brace_pos != -1:
                    start_pos = brace_pos
                elif bracket_pos != -1:
                    start_pos = bracket_pos
                else:
                    break

                try:
                    obj, end_pos = decoder.raw_decode(block, start_pos)
                    if isinstance(obj, list) and obj:
                        first_item = obj[0]
                        if isinstance(first_item, dict):
                            fn_obj = first_item.get("function") if isinstance(first_item.get("function"), dict) else first_item
                            name = fn_obj.get("name") or fn_obj.get("tool")
                            args = fn_obj.get("arguments", fn_obj.get("parameters", fn_obj.get("args", {})))
                            res = _format_res(name, args)
                            if res:
                                return res
                    elif isinstance(obj, dict):
                        fn_obj = obj.get("function") if isinstance(obj.get("function"), dict) else obj
                        name = fn_obj.get("name") or fn_obj.get("tool")
                        args = fn_obj.get("arguments", fn_obj.get("parameters", fn_obj.get("args", {})))
                        res = _format_res(name, args)
                        if res:
                            return res
                    idx = end_pos
                except json.JSONDecodeError:
                    idx = start_pos + 1

        candidate = text.strip()
        # Clean enclosing markdown fences
        if candidate.startswith("```json"):
            candidate = candidate[7:]
        elif candidate.startswith("```"):
            candidate = candidate[3:]
        if candidate.endswith("```"):
            candidate = candidate[:-3]
        candidate = candidate.strip()

        # 3. Check if text starts with a JSON list of tool calls
        if candidate.startswith("["):
            try:
                decoder = json.JSONDecoder()
                parsed_list, _ = decoder.raw_decode(candidate, 0)
                if isinstance(parsed_list, list) and parsed_list:
                    first_item = parsed_list[0]
                    if isinstance(first_item, dict):
                        fn_obj = first_item.get("function") if isinstance(first_item.get("function"), dict) else first_item
                        name = fn_obj.get("name") or fn_obj.get("tool")
                        args = fn_obj.get("arguments", fn_obj.get("parameters", fn_obj.get("args", {})))
                        res = _format_res(name, args)
                        if res:
                            return res
            except Exception:
                pass

        # 4. Iterative JSONDecoder().raw_decode starting at each '{'
        decoder = json.JSONDecoder()
        idx = 0
        while idx < len(candidate):
            brace_pos = candidate.find("{", idx)
            if brace_pos == -1:
                break
            try:
                obj, end_pos = decoder.raw_decode(candidate, brace_pos)
                if isinstance(obj, dict):
                    fn_obj = obj.get("function") if isinstance(obj.get("function"), dict) else obj
                    name = fn_obj.get("name") or fn_obj.get("tool")
                    args = fn_obj.get("arguments", fn_obj.get("parameters", fn_obj.get("args", {})))
                    res = _format_res(name, args)
                    if res:
                        return res
                idx = brace_pos + 1
            except json.JSONDecodeError:
                idx = brace_pos + 1

        # 5. Fallback regex search for single-level JSON tool call objects
        for match in re.finditer(r'\{[^{}]*"name"\s*:\s*"([^"]+)"[^{}]*\}', candidate):
            try:
                extracted = json.loads(match.group(0))
                if isinstance(extracted, dict) and "name" in extracted:
                    name = extracted["name"]
                    args = extracted.get("arguments", extracted.get("parameters", extracted.get("args", {})))
                    res = _format_res(name, args)
                    if res:
                        return res
            except Exception:
                pass

        return None

    async def generate_stream(self, payload: dict, depth: int = 0, is_retry: bool = False) -> AsyncGenerator[dict, None]:
        if depth >= 5:
            yield {"choices": [{"delta": {"content": "\n[Notice: Reached maximum autonomous ReAct steps (5).]\n"}}]}
            return

        from axiom.config import get_config
        config = get_config()
        base_url = getattr(config, "ollama_base_url", "http://127.0.0.1:11434").rstrip("/")

        if depth == 0:
            # Eagerly ensure WebExtension bridge server is running on 127.0.0.1:41144
            try:
                from axiom.tools.browser_extension import get_bridge
                bridge = get_bridge()
                if bridge.server is None:
                    asyncio.create_task(bridge.start_server())
            except Exception:
                pass

            active_win_header = await self.get_active_window_context()
            if active_win_header:
                for msg in reversed(payload.get("messages", [])):
                    if msg.get("role") == "user":
                        content = msg.get("content", "")
                        if isinstance(content, str):
                            if "[Active Window:" not in content:
                                msg["content"] = f"{active_win_header}\n{content}"
                        elif isinstance(content, list):
                            for part in content:
                                if isinstance(part, dict) and part.get("type") == "text":
                                    t = part.get("text", "")
                                    if "[Active Window:" not in t:
                                        part["text"] = f"{active_win_header}\n{t}"
                                    break
                        break

            system_prompt_content = self._build_system_prompt()

            # Query semantic memory for relevant context
            user_prompt = ""
            for msg in reversed(payload.get("messages", [])):
                if msg.get("role") == "user":
                    c = msg.get("content", "")
                    if isinstance(c, str):
                        user_prompt = c
                    elif isinstance(c, list):
                        user_prompt = " ".join(part.get("text", "") for part in c if isinstance(part, dict))
                    break

            if user_prompt:
                try:
                    from axiom.memory.semantic import search_memories
                    clean_search = re.sub(r"\[Active Window:.*?\]\n?", "", user_prompt).strip()
                    recalled = search_memories(clean_search, top_k=3)
                    if recalled:
                        mem_block = (
                            "\n\n[RECALLED SEMANTIC MEMORIES]\n"
                            "<recalled_memory>\n"
                            + "\n".join(f"- {m}" for m in recalled)
                            + "\n</recalled_memory>"
                        )
                        system_prompt_content += mem_block
                except Exception:
                    pass

            system_prompt = {
                "role": "system",
                "content": system_prompt_content,
            }

            if not payload.get("messages") or payload["messages"][0].get("role") != "system":
                payload.setdefault("messages", []).insert(0, system_prompt)
            else:
                payload["messages"][0]["content"] += f"\n\n{system_prompt_content}"

        # Apply sliding window context budgeting on every step to prevent HTTP 400 overflows
        payload["messages"] = self.prune_messages(
            payload.get("messages", []),
            max_context_tokens=self.max_context_tokens,
            reserve_tokens=1000,
        )
        user_query_for_intent = ""
        for msg in reversed(payload.get("messages", [])):
            if msg.get("role") == "user":
                c = msg.get("content", "")
                if isinstance(c, str):
                    user_query_for_intent = c
                elif isinstance(c, list):
                    user_query_for_intent = " ".join(part.get("text", "") for part in c if isinstance(part, dict))
                break
        is_interface_action = self.is_interface_action_query(user_query_for_intent)

        # Inspect query intent and filter active schemas to prevent context budget overflows
        tier = self.route_tier(user_query_for_intent)
        from axiom.core.plugins import filter_tool_schemas_by_tier
        active_tools = payload.get("tools") or get_tool_schemas(0)
        payload["tools"] = filter_tool_schemas_by_tier(active_tools, tier)

        payload["model"] = config.ollama_model

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

        # Enforce 100% GPU layer offload and adequate context size in Ollama (32K)
        options = payload.setdefault("options", {})
        if "num_ctx" not in options or options["num_ctx"] < 32768:
            options["num_ctx"] = 32768
        options.setdefault("num_gpu", 99)

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(
                    f"{base_url}/api/generate",
                    json={
                        "model": payload["model"],
                        "options": {"num_ctx": 32768, "num_gpu": 99},
                        "keep_alive": "5m",
                    },
                )
        except Exception:
            pass

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
                    buffered_chunks = []
                    buffering = (depth == 0 and not is_retry and is_interface_action) or (depth > 0)
                    refusal_detected = False

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
                                        idx = tc.get("index", 0)
                                        if idx > 0:
                                            continue  # Enforce strictly ONE tool call per response
                                        while len(pending_tool_calls) <= idx:
                                            pending_tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                                        if "id" in tc and tc["id"]:
                                            pending_tool_calls[idx]["id"] = tc["id"]
                                        if "function" in tc and isinstance(tc["function"], dict):
                                            if "name" in tc["function"] and tc["function"]["name"]:
                                                pending_tool_calls[idx]["function"]["name"] = tc["function"]["name"]
                                            if "arguments" in tc["function"] and tc["function"]["arguments"]:
                                                pending_tool_calls[idx]["function"]["arguments"] += str(tc["function"]["arguments"])
                                        elif "name" in tc and tc["name"]:
                                            pending_tool_calls[idx]["function"]["name"] = tc["name"]
                                            if "arguments" in tc and tc["arguments"]:
                                                pending_tool_calls[idx]["function"]["arguments"] += str(tc["arguments"])

                                if buffering:
                                    if "tool_calls" in delta or pending_tool_calls:
                                        buffering = False
                                        clean_so_far = "".join(collected_assistant_text)
                                        if not clean_so_far.lstrip().startswith(("{", "[", "```", "<")):
                                            for b in buffered_chunks:
                                                yield b
                                        buffered_chunks.clear()
                                        yield data
                                    else:
                                        buffered_chunks.append(data)
                                        text_so_far = "".join(collected_assistant_text)
                                        clean_text = re.sub(r"<think>.*?</think>", "", text_so_far, flags=re.DOTALL)
                                        stripped = clean_text.lstrip()
                                        if self.is_refusal(clean_text):
                                            refusal_detected = True
                                            break
                                        elif stripped and not stripped.startswith(("{", "[", "```", "<")):
                                            if depth > 0 or len(clean_text) > 250:
                                                buffering = False
                                                for b in buffered_chunks:
                                                    yield b
                                                buffered_chunks.clear()
                                        elif len(clean_text) > 4000:
                                            buffering = False
                                            for b in buffered_chunks:
                                                yield b
                                            buffered_chunks.clear()
                                else:
                                    yield data
                            except json.JSONDecodeError:
                                pass
        except httpx.ConnectError as exc:
            yield {"choices": [{"delta": {"content": f"\n⚠️ [Connection Error] Could not connect to local AI engine at {base_url}: {exc}. Ensure Ollama is running.\n"}}]}
            return
        except httpx.RequestError as exc:
            yield {"choices": [{"delta": {"content": f"\n⚠️ [Request Error] Communication failure with {base_url}: {exc}\n"}}]}
            return

        if not refusal_detected and (depth == 0 and not is_retry and is_interface_action):
            text_so_far = "".join(collected_assistant_text)
            clean_text = re.sub(r"<think>.*?</think>", "", text_so_far, flags=re.DOTALL)
            if not pending_tool_calls and self.is_refusal(clean_text):
                refusal_detected = True

        if refusal_detected:
            buffered_chunks.clear()
            collected_assistant_text.clear()
            pending_tool_calls.clear()

            override_msg = {
                "role": "user",
                "content": "[SYSTEM OVERRIDE]: You possess tools to inspect and interact with the environment. Call the appropriate tool immediately without commentary."
            }
            payload.setdefault("messages", []).append(override_msg)
            payload.setdefault("options", {})["temperature"] = 0.1
            payload["temperature"] = 0.1

            async for retry_chunk in self.generate_stream(payload, depth=depth, is_retry=True):
                yield retry_chunk
            return

        # Enforce single tool execution constraint if multiple tool calls were received
        if len(pending_tool_calls) > 1:
            pending_tool_calls = pending_tool_calls[:1]

        if not pending_tool_calls and collected_assistant_text:
            full_text = "".join(collected_assistant_text).strip()
            known_tools = set()
            if payload.get("tools"):
                for t in payload["tools"]:
                    if isinstance(t, dict):
                        if "function" in t and "name" in t["function"]:
                            known_tools.add(t["function"]["name"])
                        elif "name" in t:
                            known_tools.add(t["name"])

            tool_call = self.extract_first_tool_call(full_text, known_tools)
            if tool_call:
                func_name = tool_call.get("function", {}).get("name") or tool_call.get("name")
                func_args = tool_call.get("function", {}).get("arguments") or tool_call.get("arguments", {})
                if isinstance(func_args, str):
                    try:
                        func_args = json.loads(func_args)
                    except Exception:
                        pass
                if not isinstance(func_args, dict):
                    func_args = {}
                func_args_str = json.dumps(func_args)
                call_id = "call_native_0"
                pending_tool_calls = [{
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": func_name,
                        "arguments": func_args_str
                    },
                    "name": func_name,
                    "arguments": func_args
                }]
                buffered_chunks.clear()
                yield {
                    "choices": [{
                        "delta": {
                            "tool_calls": [{
                                "index": 0,
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
                collected_assistant_text = []

        if not pending_tool_calls and buffered_chunks:
            for b in buffered_chunks:
                yield b
            buffered_chunks.clear()

        if pending_tool_calls:
            assistant_msg = {
                "role": "assistant",
                "content": "".join(collected_assistant_text) if collected_assistant_text else None,
                "tool_calls": pending_tool_calls
            }
            payload["messages"].append(assistant_msg)

            for tc in pending_tool_calls:
                func_name = tc.get("function", {}).get("name") or tc.get("name")
                func_args_raw = tc.get("function", {}).get("arguments") or tc.get("arguments", {})
                tool_call_id = tc.get("id", "call_native_0")

                if isinstance(func_args_raw, str):
                    try:
                        func_args = json.loads(func_args_raw) if func_args_raw else {}
                    except Exception:
                        func_args = {}
                elif isinstance(func_args_raw, dict):
                    func_args = func_args_raw
                else:
                    func_args = {}

                # Guard against model confusing interact_with_ui with interact_with_browser on web elements
                if func_name == "interact_with_ui" and ("element_id" in func_args or func_args.get("action") in ("click_element", "fill_element")):
                    func_name = "interact_with_browser"

                timeout = get_tier_timeout(func_name)
                timeout_int = int(timeout)
                try:
                    tool_result = await asyncio.wait_for(
                        self.execute_tool(func_name, **func_args),
                        timeout=timeout,
                    )
                    
                    if not isinstance(tool_result, str):
                        tool_result = json.dumps(tool_result, indent=2)
                    res_str = tool_result
                except (TimeoutError, asyncio.TimeoutError):
                    res_str = json.dumps({
                        "success": False,
                        "error": f"Tool execution timed out after {timeout_int}s. Try a faster Tier 1 command or verify active window.",
                    })
                except Exception as e:
                    res_str = json.dumps({"error": str(e), "status": "tool_execution_failed"})

                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": func_name,
                    "content": res_str
                }
                payload["messages"].append(tool_msg)

                session_id = payload.get("session_id")
                if session_id:
                    try:
                        from axiom.db.memory import add_message
                        add_message(session_id, "tool", f"[{func_name}] {res_str}")
                    except Exception:
                        pass

            if depth < 5:
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

        # Tier 1 indicators (Window management & Hyprland IPC, Process, Clipboard, Journal, Media, Notifications, Network, Files)
        tier1_patterns = [
            r"\b(window|windows|workspace|workspaces|fullscreen|floating|tile|tiling)\b",
            r"\b(focus|switch to|move to|close)\s+(window|workspace)\b",
            r"\b(active window|list windows|hyprctl|hyprland)\b",
            r"\b(process|processes|pid|kill\s+process|kill\s+pid|journal|journalctl|systemd|clipboard|wl-copy|wl-paste)\b",
            r"\b(notify|notification|notify-send|alert)\b",
            r"\b(network|gateway|ip\s+address|interfaces|tailscale|dns|ping|vpn|wifi)\b",
            r"\b(media|music|playerctl|playback|volume|track|song|mpris)\b",
            r"\b(file|files|patch|rollback|undo|backup)\b",
            r"\b(command|bash|shell|terminal|exec|run command|cli)\b",
        ]
        for pattern in tier1_patterns:
            if re.search(pattern, task_lower):
                return "tier1_ipc"

        # Tier 2 indicators (Web browser, DOM, CDP, web apps)
        tier2_patterns = [
            r"\b(browser|chrome|chromium|brave|zen|firefox|monkeytype|gemini|youtube|electron)\b",
            r"\b(dom|html|css selector|website|webpage|web page|web app|tab|url|href)\b",
            r"\b(inspect|evaluate|javascript|js)\b",
            r"\b(scroll|scroll_page|extract_page_content|extract\s+page|page\s+content|markdown|read\s+article|pin\s+tab|duplicate\s+tab|reload\s+tab)\b",
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
        task_lower = task_description.lower()
        if tier == "tier1_ipc":
            if any(k in task_lower for k in ("clipboard", "wl-copy", "wl-paste", "copy to clipboard", "paste")):
                return "manage_system_clipboard"
            if any(k in task_lower for k in ("journal", "journalctl", "systemd log", "service log")):
                return "query_system_journal"
            if any(k in task_lower for k in ("process", "pid", "kill")):
                return "manage_system_process"
            if any(k in task_lower for k in ("notify", "notification", "alert")):
                return "send_desktop_notification"
            if any(k in task_lower for k in ("network", "gateway", "tailscale", "dns", "ping", "vpn")):
                return "inspect_network"
            if any(k in task_lower for k in ("media", "music", "volume", "playerctl", "playback")):
                return "manage_media_playback"
            if any(k in task_lower for k in ("file", "rollback", "undo", "patch")):
                return "manage_workspace_file"
            return "manage_desktop_window"
        tier_map = {
            "tier1_ipc": "manage_desktop_window",
            "tier2_browser": "interact_with_browser",
            "tier3_vision": "interact_with_ui",
        }
        return tier_map.get(tier, "interact_with_ui")

