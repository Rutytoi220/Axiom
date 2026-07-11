"""Orchestrator agent with a stable state-machine tool-calling loop."""

import asyncio
import json
import logging
import hashlib
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional

from axiom.agents.echo_agent import SimpleBaseAgent
from axiom.agents.base import AgentResult

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 10
LLM_RETRIES = 3


class AgentState(str, Enum):
    THINK = "THINK"
    ACT = "ACT"
    OBSERVE = "OBSERVE"
    REFLECT = "REFLECT"
    EXIT = "EXIT"


@dataclass
class Plan:
    objective: str
    steps: List[str] = field(default_factory=list)
    current_step: int = 0
    completion_condition: str = "Provide a concise final answer that satisfies the objective."

    def current(self) -> str:
        if not self.steps:
            return self.objective
        return self.steps[min(self.current_step, len(self.steps) - 1)]


class OrchestratorAgent(SimpleBaseAgent):
    """AI agent that uses an LLM + registered tools to accomplish tasks."""

    def __init__(self, registry=None, bus=None, memory=None, llm=None):
        super().__init__(name="orchestrator", registry=registry, bus=bus, memory=memory)
        self._agents = {}
        self._llm = llm
        self._chat_history: List[Dict[str, str]] = []
        self._state = "idle"

    @property
    def description(self) -> str:
        """Human-readable summary for introspection (e.g. the CLI's `agents` command)."""
        return "LLM-driven orchestrator agent that plans, calls tools, and synthesizes a final answer."

    def set_llm(self, llm) -> None:
        self._llm = llm

    def register_agent(self, agent) -> None:
        self._agents[agent.name] = agent
        if self.registry is not None:
            if hasattr(self.registry, 'register_agent'):
                self.registry.register_agent(f"agent.{agent.name}", agent)
            elif hasattr(self.registry, 'register'):
                self.registry.register(f"agent.{agent.name}", agent)

    def list_agents(self) -> List[str]:
        return sorted(self._agents.keys())

    def run(self, task: str, use_tools: bool = True, session_id: Optional[str] = None) -> AgentResult:
        self._execution_count += 1
        self._state = "running"
        try:
            self._emit("orchestrator.task.received", {"task": task, "session_id": session_id})
            steps: List[str] = []
            if self._llm is None:
                return self._prefix_route(task, steps)
            return self._agentic_loop(task, steps, use_tools=use_tools, session_id=session_id)
        finally:
            self._state = "idle"

    def _agentic_loop(self, task: str, steps: List[str], use_tools: bool = True, session_id: Optional[str] = None) -> AgentResult:
        session_id = str(session_id or uuid.uuid4())
        plan = self._load_plan(session_id) or self._create_plan(task)
        state = AgentState.THINK
        tool_schemas = self._get_tool_schemas() if use_tools else []
        observations: List[Dict[str, Any]] = []
        final_response = ""
        rounds = 0

        self._persist_step(session_id, "user", {"task": task})
        self._log(f"Session {session_id}: starting state machine", steps)

        try:
            if hasattr(self._llm, "is_available") and not self._llm.is_available():
                return AgentResult(False, error="Ollama is not running. Start it with: ollama serve", steps_taken=steps)
        except Exception as exc:
            self._log(f"LLM availability check failed, continuing: {exc}", steps)

        while state != AgentState.EXIT and rounds < MAX_TOOL_ROUNDS:
            rounds += 1
            self._persist_step(session_id, "state", {"state": state.value, "plan": asdict(plan), "round": rounds})

            if state == AgentState.THINK:
                self._log(f"THINK round {rounds}: {plan.current()}", steps)
                messages = self._build_messages(task, plan, observations, session_id)
                response_msg = self._call_llm(messages, tool_schemas)
                self._persist_step(session_id, "reasoning", response_msg)
                tool_calls = response_msg.get("tool_calls") or []
                if tool_calls and use_tools:
                    state = AgentState.ACT
                    pending_calls = tool_calls
                    assistant_msg = response_msg
                else:
                    final_response = response_msg.get("content") or "Task completed."
                    state = AgentState.REFLECT

            elif state == AgentState.ACT:
                executed_tool_ids_this_round = set()
                for tc in pending_calls:
                    tool_name, arguments, tc_id = self._normalize_tool_call(tc)
                    sig = tc_id or hashlib.md5(f"{tool_name}:{json.dumps(arguments, sort_keys=True, default=str)}".encode()).hexdigest()
                    if sig in executed_tool_ids_this_round:
                        result = self._structured_tool_result(tool_name, arguments, {"error": "Duplicate tool call skipped for this inference step."}, False)
                    else:
                        executed_tool_ids_this_round.add(sig)
                        result = self._execute_tool(tool_name, arguments)
                    observations.append(result)
                    self._persist_step(session_id, "tool_result", result)
                    self._log(f"ACT {tool_name}: success={result.get('success')}", steps)
                state = AgentState.OBSERVE

            elif state == AgentState.OBSERVE:
                self._log("OBSERVE: incorporated latest tool results", steps)
                self._persist_step(session_id, "observation", {"observations": observations[-3:]})
                state = AgentState.REFLECT

            elif state == AgentState.REFLECT:
                reflection = self._reflect(task, plan, observations, final_response)
                self._persist_step(session_id, "reflection", reflection)
                if reflection.get("complete") or final_response:
                    final_response = final_response or reflection.get("answer") or "Task completed."
                    state = AgentState.EXIT
                else:
                    plan.current_step = min(plan.current_step + 1, max(len(plan.steps) - 1, 0))
                    state = AgentState.THINK
                self._save_plan(session_id, plan)

        if not final_response:
            final_response = "Task processing reached maximum rounds. Review tool results for partial progress."
        self._chat_history = (self._chat_history + [{"role": "user", "content": task}, {"role": "assistant", "content": final_response}])[-20:]
        self._persist_step(session_id, "assistant", {"response": final_response})
        self._emit("orchestrator.task.completed", {"task": task, "success": True, "rounds": rounds, "session_id": session_id})
        return AgentResult(True, output={"response": final_response, "tool_results": observations, "rounds": rounds, "session_id": session_id, "plan": asdict(plan)}, steps_taken=steps)

    def _build_messages(self, task: str, plan: Plan, observations: List[Dict[str, Any]], session_id: str) -> List[Dict[str, Any]]:
        memories = self._retrieve_relevant_memory(task, session_id, top_k=6)
        return [
            {"role": "system", "content": "You are AXIOM, a local-first autonomous agent. Operate on the plan. Use tools only when needed. Return a final answer when complete."},
            {"role": "system", "content": json.dumps({"plan": asdict(plan), "relevant_memory": memories, "recent_observations": observations[-5:]}, default=str)},
            {"role": "user", "content": task},
        ]

    def _call_llm(self, messages: List[Dict[str, Any]], tool_schemas: List[Dict[str, Any]]) -> Dict[str, Any]:
        last_exc = None
        for attempt in range(LLM_RETRIES):
            try:
                if tool_schemas and hasattr(self._llm, "chat_with_tools"):
                    msg = self._llm.chat_with_tools(messages, tool_schemas)
                    return msg if isinstance(msg, dict) else {"role": "assistant", "content": str(msg)}
                content = self._llm.chat(messages)
                return {"role": "assistant", "content": content or ""}
            except Exception as exc:
                last_exc = exc
                time.sleep(min(2 ** attempt, 8) * 0.25)
        return {"role": "assistant", "content": f"LLM call failed after retries: {last_exc}"}

    def _normalize_tool_call(self, tc: Dict[str, Any]) -> tuple[str, Dict[str, Any], str]:
        func = tc.get("function", {}) if isinstance(tc, dict) else {}
        tool_name = func.get("name") or tc.get("name") or "unknown"
        arguments = func.get("arguments", tc.get("arguments", {}))
        if isinstance(arguments, str):
            arguments = self._safe_json_obj(arguments)
        if not isinstance(arguments, dict):
            arguments = {"input": arguments}
        tc_id = tc.get("id") or f"call_{hashlib.md5(f'{tool_name}:{json.dumps(arguments, sort_keys=True, default=str)}'.encode()).hexdigest()}"
        return tool_name, arguments, tc_id

    def _safe_json_obj(self, text: str) -> Dict[str, Any]:
        raw = text.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", raw, flags=re.DOTALL | re.IGNORECASE)
        if fence:
            raw = fence.group(1).strip()
        if not raw.startswith("{"):
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            raw = match.group(0) if match else raw
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"input": parsed}
        except Exception:
            return {"input": text}

    def _create_plan(self, task: str) -> Plan:
        return Plan(objective=task, steps=["Understand the objective", "Use tools if needed", "Synthesize final answer"], current_step=0)

    def _reflect(self, task: str, plan: Plan, observations: List[Dict[str, Any]], final_response: str) -> Dict[str, Any]:
        if final_response:
            return {"complete": True, "answer": final_response, "reason": "LLM produced final response"}
        if observations and not observations[-1].get("success", False):
            return {"complete": False, "reason": "Latest tool failed, another plan step may be needed"}
        if observations and plan.current_step >= len(plan.steps) - 1:
            return {"complete": False, "reason": "Need synthesis after tool observations"}
        return {"complete": False, "reason": "Continue plan"}

    def _get_tool_schemas(self) -> List[Dict[str, Any]]:
        schemas: List[Dict[str, Any]] = []
        tools = self.registry.list_tools() if self.registry and hasattr(self.registry, "list_tools") else {}
        for tool_id, tool in tools.items():
            tool_schema = getattr(tool, "schema", None)
            if isinstance(tool_schema, dict):
                schemas.append({"type": "function", "function": {"name": tool_id, "description": getattr(tool, "description", tool_id), "parameters": tool_schema}})
        return schemas

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tools = self.registry.list_tools() if self.registry and hasattr(self.registry, "list_tools") else {}
        tool = tools.get(tool_name) or next((t for t in tools.values() if getattr(t, "name", None) == tool_name), None)
        if not tool:
            return self._structured_tool_result(tool_name, arguments, {"error": f"Tool not found: {tool_name}"}, False)
        try:
            result = tool.execute(arguments)
            if asyncio.iscoroutine(result):
                result = self._run_coro_sync(result)
            if isinstance(result, dict) and {"tool", "arguments", "result", "success"}.issubset(result.keys()):
                return result
            payload = {"output": getattr(result, "output", result), "error": getattr(result, "error", None)}
            return self._structured_tool_result(tool_name, arguments, payload, bool(getattr(result, "success", True)))
        except Exception as exc:
            return self._structured_tool_result(tool_name, arguments, {"error": str(exc)}, False)

    def _structured_tool_result(self, tool: str, arguments: Dict[str, Any], result: Dict[str, Any], success: bool) -> Dict[str, Any]:
        return {"tool": tool, "arguments": arguments if isinstance(arguments, dict) else {"input": arguments}, "result": result if isinstance(result, dict) else {"output": result}, "success": bool(success)}

    def _run_coro_sync(self, coro):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                new_loop = asyncio.new_event_loop()
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    def _persist_step(self, session_id: str, kind: str, payload: Any) -> None:
        if not self.memory:
            return
        try:
            key = f"session:{session_id}:step:{time.time_ns()}:{kind}"
            if hasattr(self.memory, "set"):
                self.memory.set(key, {"kind": kind, "payload": payload, "timestamp": time.time()}, tags=["session", session_id, kind])
            if hasattr(self.memory, "log_event"):
                self.memory.log_event(f"orchestrator.{kind}", {"session_id": session_id, "payload": payload}, source="orchestrator")
        except Exception as exc:
            logger.debug("Failed to persist step: %s", exc)

    def _retrieve_relevant_memory(self, task: str, session_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.memory or not hasattr(self.memory, "search"):
            return []
        terms = [w.lower() for w in re.findall(r"[a-zA-Z0-9_]{4,}", task)][:12]
        try:
            rows = self.memory.search([session_id]) + self.memory.search(["session"])
        except Exception:
            return []
        scored = []
        for row in rows:
            text = json.dumps(row.get("value", row), default=str).lower()
            score = sum(1 for term in terms if term in text)
            if score:
                scored.append((score, row))
        return [row for _, row in sorted(scored, key=lambda x: x[0], reverse=True)[:top_k]]

    def _save_plan(self, session_id: str, plan: Plan) -> None:
        if self.memory and hasattr(self.memory, "set"):
            try:
                self.memory.set(f"session:{session_id}:plan", asdict(plan), tags=["session", session_id, "plan"])
            except Exception:
                pass

    def _load_plan(self, session_id: str) -> Optional[Plan]:
        if self.memory and hasattr(self.memory, "get"):
            try:
                data = self.memory.get(f"session:{session_id}:plan")
                if isinstance(data, dict):
                    return Plan(**data)
            except Exception:
                return None
        return None

    def _prefix_route(self, task: str, steps: List[str]) -> AgentResult:
        prefix, subtask = (task.split(":", 1) if ":" in task else (None, task))
        prefix = prefix.strip() if prefix else None
        subtask = subtask.strip()
        agent = self._agents.get("echo_agent") if prefix == "echo" else None
        if agent is not None:
            self._log(f"Routing to agent: {agent.name}", steps)
            result = agent.run(subtask)
            return AgentResult(getattr(result, 'success', True), output=getattr(result, 'output', None), error=getattr(result, 'error', None), steps_taken=steps + getattr(result, 'steps_taken', []))
        return AgentResult(False, error=f"No agent matched for: {task}", steps_taken=steps)
