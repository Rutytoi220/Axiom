import re

with open('axiom/agents/orchestrator_agent.py', 'r') as f:
    code = f.read()

# Hoist NeuralRouter
router_block = """
                # [NEW] NeuralRouter Integration
                available_models = []
                if hasattr(self._llm, '_get_installed_models'):
                    available_models = self._llm._get_installed_models()
                elif hasattr(self._llm, 'models'):
                    available_models = self._llm.models
                    
                if available_models:
                    try:
                        import asyncio
                        from axiom.engine.adaptive_router import NeuralRouter
                        
                        async def _run_router():
                            router = NeuralRouter()
                            return await router.route(task_type=intent, user_prompt=task, available_models=available_models)
                            
                        try:
                            loop = asyncio.get_running_loop()
                            import concurrent.futures
                            future = asyncio.run_coroutine_threadsafe(_run_router(), loop)
                            best_model = future.result(timeout=10.0)
                        except RuntimeError:
                            best_model = asyncio.run(_run_router())
                            
                        if best_model and hasattr(self._llm, 'config'):
                            self._llm.config.model = f"ollama/{best_model}" if not best_model.startswith("ollama/") else best_model
                            logger.info(f"[NeuralRouter] Dynamically routed to: {best_model}")
                    except Exception as e:
                        logger.warning(f"NeuralRouter integration failed, falling back to legacy routing: {e}")
"""

# Extract the block
if router_block.strip() in code:
    code = code.replace(router_block, "")
    
# Insert before the while loop (around txn.begin())
insertion_point = "        txn.begin()"
if insertion_point in code:
    # Adjust indentation
    indented_router = "\n".join("        " + line.strip() if line.strip() else "" for line in router_block.split("\n"))
    code = code.replace(insertion_point, indented_router + "\n" + insertion_point)

# Hoist TelemetryDB
telemetry_block = """
                # [NEW] NeuralRouter Telemetry Loop
                try:
                    latency = (time.perf_counter() - round_start_time)
                    success_score = 1 if response_msg.get('tool_calls') or response_msg.get('content') else 0
                    
                    current_model = getattr(getattr(self._llm, 'config', None), 'model', 'unknown').replace("ollama/", "")
                    
                    async def _log_telemetry():
                        from axiom.engine.adaptive_router import TelemetryDB
                        db = TelemetryDB()
                        await db.update_metrics(current_model, intent, latency, success_score)
                        
                    try:
                        loop = asyncio.get_running_loop()
                        asyncio.run_coroutine_threadsafe(_log_telemetry(), loop)
                    except RuntimeError:
                        # Fallback for synchronous thread environment (like standard CLI testing)
                        asyncio.run(_log_telemetry())
                except Exception as e:
                    logger.warning(f"Failed to log routing telemetry: {e}")
"""

if telemetry_block.strip() in code:
    code = code.replace(telemetry_block, "")

# Insert telemetry after the while loop breaks
end_loop_point = "        if not final_response:"
if end_loop_point in code:
    # Adjust indentation
    indented_telemetry = "\n".join("        " + line.strip() if line.strip() else "" for line in telemetry_block.split("\n"))
    code = code.replace(end_loop_point, indented_telemetry + "\n" + end_loop_point)

# Update MAX_TOOL_ROUNDS to MAX_STEPS = 5 in the while loop
code = code.replace("while state != AgentState.EXIT and rounds < MAX_TOOL_ROUNDS:", "MAX_STEPS = 5\n        while state != AgentState.EXIT and rounds < MAX_STEPS:")
code = code.replace("total_steps': MAX_TOOL_ROUNDS", "total_steps': MAX_STEPS")

# Modify state machine transitions to enable ReAct
code = code.replace("state = AgentState.REFLECT", "state = AgentState.EXIT")
# When we want to force synthesis on large doc, it already does state = AgentState.THINK.
# But for normal observe, we want it to go back to THINK.
code = code.replace("else:\n                    state = AgentState.EXIT\n            elif state == AgentState.REFLECT", "else:\n                    state = AgentState.THINK\n            elif state == AgentState.REFLECT")

with open('axiom/agents/orchestrator_agent.py', 'w') as f:
    f.write(code)

