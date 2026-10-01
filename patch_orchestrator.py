import re

with open('axiom/agents/orchestrator_agent.py', 'r') as f:
    code = f.read()

# 1. Modify _execute_tool payload interceptor
old_intercept = """        out_str = result_dict.get('result', {}).get('output')
        if isinstance(out_str, str) and out_str.startswith("SCREENSHOT_BASE64:"):
            b64 = out_str.replace("SCREENSHOT_BASE64:", "")
            result_dict['result']['output'] = {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Here is the screenshot. Where are the coordinates for the target?"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                ]
            }"""

new_intercept = """        out_str = result_dict.get('result', {}).get('output')
        if isinstance(out_str, str) and out_str.startswith("SCREENSHOT_BASE64:"):
            b64 = out_str.replace("SCREENSHOT_BASE64:", "")
            if "," in b64: b64 = b64.split(",", 1)[1]
            result_dict['result']['output'] = "[SCREENSHOT CAPTURED AND ATTACHED TO VISION PAYLOAD]"
            result_dict['_vision_b64'] = b64
        elif isinstance(out_str, dict) and "image_b64" in out_str:
            b64 = out_str.pop("image_b64")
            if "," in b64: b64 = b64.split(",", 1)[1]
            out_str["message"] = out_str.get("message", "") + " [SCREENSHOT CAPTURED AND ATTACHED TO VISION PAYLOAD]"
            result_dict['_vision_b64'] = b64"""

code = code.replace(old_intercept, new_intercept)

# 2. Modify the main loop to extract _vision_b64 and inject it into messages
old_loop = """                try:
                    from axiom.memory.compression import ObservationCompressor
                    observations = ObservationCompressor.compress_observations_buffer(observations, iterations=rounds)
                except Exception as _buf_err:
                    logger.warning("Failed to compress observation buffer: %s", _buf_err)
                messages = self._context_manager.build_context_window(system_messages=system_messages, chat_history=self._chat_history, current_task=task, retrieved_memories=memories, observations=observations)
                current_schemas = tool_schemas"""

new_loop = """                try:
                    from axiom.memory.compression import ObservationCompressor
                    observations = ObservationCompressor.compress_observations_buffer(observations, iterations=rounds)
                except Exception as _buf_err:
                    logger.warning("Failed to compress observation buffer: %s", _buf_err)
                
                # Extract vision payloads safely before stringification
                vision_payloads = []
                for obs in observations:
                    if '_vision_b64' in obs:
                        vision_payloads.append(obs.pop('_vision_b64'))
                        
                messages = self._context_manager.build_context_window(system_messages=system_messages, chat_history=self._chat_history, current_task=task, retrieved_memories=memories, observations=observations)
                
                if vision_payloads:
                    for msg in reversed(messages):
                        if msg.get('role') == 'user':
                            msg['images'] = msg.get('images', []) + vision_payloads
                            break
                    else:
                        messages.append({'role': 'user', 'content': 'Please analyze the attached screen captures.', 'images': vision_payloads})
                        
                current_schemas = tool_schemas"""

code = code.replace(old_loop, new_loop)

# 3. Clean up the manual vision_images kwarg that is breaking Ollama
old_vision = """                vision_images = []
                if intent == 'vision':
                    try:
                        from axiom.tools.desktop.capture import DesktopCapture
                        b64 = DesktopCapture.capture_b64()
                        if b64:
                            vision_images.append({'url': f'data:image/png;base64,{b64}'})
                            self._log('[Vision] Attached live desktop screenshot to model context.', steps)
                    except Exception as err:
                        self._log(f'[Vision] Failed to capture screenshot: {err}', steps)
                try:
                    self._log(f'LLM Call initiated (temperature={temp_override})...', steps)
                    import copy
                    current_schemas = copy.deepcopy(tool_schemas)
                except Exception:
                    pass
                response_msg = self._call_llm(messages, current_schemas, timeout=time_left, temperature=temp_override, images=vision_images)"""

new_vision = """                if intent == 'vision':
                    try:
                        from axiom.tools.desktop.capture import DesktopCapture
                        b64 = DesktopCapture.capture_b64()
                        if b64:
                            if "," in b64: b64 = b64.split(",", 1)[1]
                            for msg in reversed(messages):
                                if msg.get('role') == 'user':
                                    msg['images'] = msg.get('images', []) + [b64]
                                    break
                            else:
                                messages.append({'role': 'user', 'content': 'Live desktop context:', 'images': [b64]})
                            self._log('[Vision] Attached live desktop screenshot to model context.', steps)
                    except Exception as err:
                        self._log(f'[Vision] Failed to capture screenshot: {err}', steps)
                try:
                    self._log(f'LLM Call initiated (temperature={temp_override})...', steps)
                    import copy
                    current_schemas = copy.deepcopy(tool_schemas)
                except Exception:
                    pass
                response_msg = self._call_llm(messages, current_schemas, timeout=time_left, temperature=temp_override)"""

code = code.replace(old_vision, new_vision)

with open('axiom/agents/orchestrator_agent.py', 'w') as f:
    f.write(code)
