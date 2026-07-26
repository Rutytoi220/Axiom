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
from axiom.agents.simple_base import SimpleBaseAgent
from axiom.agents.base import AgentResult
from axiom.memory.context_manager import ContextManager, estimate_messages_tokens
from axiom.core.transaction import WorkspaceTransactionManager, StagingCapExceeded
from axiom.engine.telemetry import HardwareTelemetryDaemon
from axiom.engine.router import SmartRouter
from axiom.engine.tool_pruner import ToolPruner
from axiom.swarm.consensus import ConsensusEngine
logger = logging.getLogger(__name__)
MAX_TOOL_ROUNDS = 40
LLM_RETRIES = 3
DOCUMENT_EXTRACTION_NOTICE = '[Document Extraction Notice]: Zero selectable characters found in {file_path}. This document may be encrypted, security-locked, or rendered as a flat image scan lacking a readable text layer. Please convert via OCR.'
PRUNED_ECHO_INDICATOR = '[System: Pruned duplicate model echo -> Retrying...]'
CHAT_ECHO_RETRY_FALLBACK = 'I apologize, my conversational buffer stuttered. Could you repeat or rephrase that?'
CHAT_ECHO_RETRY_PROMPT = '[System: Duplicate assistant response pruned.] Generate a substantively fresh answer to the latest user message. Do not repeat the previous answer and do not mention this retry.'
INTERNAL_OBSERVATION_PREFIXES = ('[system notice]', '[system warn]', '[system notice:')
DIRECT_ACTION_MODE_GUARD = "CRITICAL EXECUTION RULE: You are operating in Direct Action Mode. You are STRICTLY FORBIDDEN from outputting introductory greetings, self-identifications, or capability recitals (e.g., DO NOT say 'I am AXIOM', 'Here is what I can do', or 'How can I assist you today'). If a user requests a file check or system action, emit ONLY the required tool call syntax or immediate analytical findings."

class AgentState(str, Enum):
    """Auto-generated docstring.

"""
    THINK = 'THINK'
    ACT = 'ACT'
    OBSERVE = 'OBSERVE'
    REFLECT = 'REFLECT'
    EXIT = 'EXIT'

@dataclass
class Plan:
    """Auto-generated docstring.

"""
    objective: str
    steps: List[str] = field(default_factory=list)
    current_step: int = 0
    completion_condition: str = 'Provide a concise final answer that satisfies the objective.'

    def current(self) -> str:
        """Auto-generated docstring.


Returns:
    Return value.
"""
        if not self.steps:
            return self.objective
        return self.steps[min(self.current_step, len(self.steps) - 1)]

class OrchestratorAgent(SimpleBaseAgent):
    """AI agent that uses an LLM + registered tools to accomplish tasks."""

    def __init__(self, registry=None, bus=None, memory=None, llm=None, context_manager=None):
        """Auto-generated docstring.

Args:
    registry: Argument.
    bus: Argument.
    memory: Argument.
    llm: Argument.
    context_manager: Argument.

Returns:
    Return value.
"""
        super().__init__(name='orchestrator', registry=registry, bus=bus, memory=memory)
        self._agents = {}
        self._chat_history: List[Dict[str, str]] = []
        self._state = 'idle'
        self._context_manager = context_manager or ContextManager()
        self.telemetry_daemon = None
        if bus:
            self.telemetry_daemon = HardwareTelemetryDaemon(event_bus=bus)
            self.telemetry_daemon.start()
        if llm is not None:
            if getattr(llm, '_is_mock', False) or 'Mock' in type(llm).__name__:
                self._llm = llm
            else:
                self._llm = SmartRouter(llm, self.telemetry_daemon, getattr(self, 'event_bus', None))
        else:
            self._llm = None

    @property
    def description(self) -> str:
        """Human-readable summary for introspection (e.g. the CLI's `agents` command)."""
        return 'LLM-driven orchestrator agent that plans, calls tools, and synthesizes a final answer.'

    def set_llm(self, llm) -> None:
        """Auto-generated docstring.

Args:
    llm: Argument.

Returns:
    Return value.
"""
        if getattr(llm, '_is_mock', False) or 'Mock' in type(llm).__name__:
            self._llm = llm
        else:
            self._llm = SmartRouter(llm, self.telemetry_daemon, getattr(self, 'event_bus', None))

    def register_agent(self, agent) -> None:
        """Auto-generated docstring.

Args:
    agent: Argument.

Returns:
    Return value.
"""
        self._agents[agent.name] = agent
        if self.registry is not None and hasattr(self.registry, 'register_agent'):
            self.registry.register_agent(f'agent.{agent.name}', agent)

    def list_agents(self) -> List[str]:
        """Auto-generated docstring.


Returns:
    Return value.
"""
        return sorted(self._agents.keys())

    def run(self, task: str, use_tools: bool=True, session_id: Optional[str]=None, timeout: Optional[float]=None) -> AgentResult:
        """Auto-generated docstring.

Args:
    task: Argument.
    use_tools: Argument.
    session_id: Argument.
    timeout: Argument.

Returns:
    Return value.
"""
        self._execution_count += 1
        self._state = 'running'
        try:
            self._emit('orchestrator.task.received', {'task': task, 'session_id': session_id})
            steps: List[str] = []
            if self._llm is None:
                return self._prefix_route(task, steps)
            return self._agentic_loop(task, steps, use_tools=use_tools, session_id=session_id, timeout=timeout)
        finally:
            self._state = 'idle'

    def _agentic_loop(self, task: str, steps: List[str], use_tools: bool=True, session_id: Optional[str]=None, timeout: Optional[float]=None) -> AgentResult:
        """Auto-generated docstring.

Args:
    task: Argument.
    steps: Argument.
    use_tools: Argument.
    session_id: Argument.
    timeout: Argument.

Returns:
    Return value.
"""
        session_id = str(session_id or uuid.uuid4())
        plan = self._load_plan(session_id) or self._create_plan(task)
        state = AgentState.THINK
        intent = 'orchestration'
        raw_intent = getattr(self._llm, 'intent', None)
        if raw_intent and type(raw_intent).__name__ != 'Mock':
            if hasattr(raw_intent, 'value'):
                intent = raw_intent.value
            else:
                intent = raw_intent
        elif hasattr(self._llm, '_classify_task'):
            _classification = self._llm._classify_task([{'role': 'user', 'content': task}])
            intent_str = getattr(_classification, 'value', str(_classification)).lower()
            if intent_str == 'system':
                intent = 'orchestration'
            elif type(intent_str).__name__ != 'Mock':
                intent = intent_str
        if type(intent).__name__ == 'Mock':
            intent = 'orchestration'
        if intent == 'chat':
            use_tools = False
            self._log("Task intent is 'chat'. Conditionally disabling tools for rapid response.", steps)
        raw_schemas = self._get_tool_schemas() if use_tools else []
        tool_schemas = ToolPruner.prune_schemas(task, raw_schemas, intent)
        dropped = len(raw_schemas) - len(tool_schemas)
        if dropped > 0:
            self._log(f"[Schema Pruner]: Dropped {dropped} irrelevant tools. Active context: {[t.get('name') for t in tool_schemas]}", steps)
        observations: List[Dict[str, Any]] = []
        final_response = ''
        accumulated_response = ''
        rounds = 0
        timeout = timeout if timeout is not None else 600.0
        deadline = time.time() + timeout
        self._tool_call_history = []
        override_prompt = None
        force_text_response = False
        txn = WorkspaceTransactionManager(bus=self._bus if hasattr(self, '_bus') else getattr(self, 'bus', None), verbose=True)
        txn.begin()
        self._persist_step(session_id, 'user', {'task': task})
        self._log(f'Session {session_id}: starting state machine', steps)
        try:
            if hasattr(self._llm, 'is_available') and (not self._llm.is_available()):
                txn.rollback()
                return AgentResult(False, error='Ollama is not running. Start it with: ollama serve', steps_taken=steps)
        except Exception as exc:
            self._log(f'LLM availability check failed, continuing: {exc}', steps)
        executed_signatures: set[str] = set()
        while state != AgentState.EXIT and rounds < MAX_TOOL_ROUNDS:
            if deadline and time.time() > deadline:
                final_response = 'Task processing timed out.'
                self._log('Task timed out before completion.', steps)
                self._emit('plan.failed', {'reason': 'timeout', 'step': rounds, 'total_steps': MAX_TOOL_ROUNDS})
                txn.rollback()
                break
            rounds += 1
            round_start_time = time.perf_counter()
            self._persist_step(session_id, 'state', {'state': state.value, 'plan': asdict(plan), 'round': rounds})
            if state == AgentState.THINK:
                self._log(f'THINK round {rounds}: {plan.current()}', steps)
                messages = self._build_messages(task, plan, observations, session_id, override_prompt, intent=intent)
                override_prompt = None
                time_left = max(1.0, deadline - time.time()) if deadline else 60.0
                temp_override = 0.1 if intent in ('orchestration', 'code') else None
                current_schemas = [] if force_text_response else tool_schemas
                response_msg = self._call_llm(messages, current_schemas, timeout=time_left, temperature=temp_override)
                force_text_response = False
                tool_calls = response_msg.get('tool_calls') or []
                content = response_msg.get('content')
                logger.debug("RAW CONTENT: %r TOOL_CALLS: %s", content, tool_calls)
                import re, json
                if not tool_calls and content and use_tools:
                    pattern_python = '(\\w+)\\s*\\(["\\\']?(.*?)["\\\']?\\)'
                    pattern_md = '\\*\\*?(\\w+)\\*\\*?.*?```(?:json|text)?\\s*([^\\n`]+)\\s*```'
                    pattern_colon = '(?:Tool|Call|Action):\\s*(\\w+).*?([/\\w\\-. ]+\\.\\w+)'
                    pattern_link = '\\[(\\w+)\\]\\(([^)]+)\\)'
                    pattern_paren_json = '\\(?(\\w+)\\s*:\\s*(\\{[^}]+\\}|[^\\)]+)\\)?'
                    pattern_native_json = '\\{\\s*"(?:name|tool)"\\s*:\\s*"([^"]+)"\\s*,\\s*"arguments"\\s*:\\s*(\\{.*?\\})\\s*\\}'
                    match = None
                    for pattern in (pattern_python, pattern_md, pattern_colon, pattern_link, pattern_paren_json, pattern_native_json):
                        m = re.search(pattern, str(content), flags=re.IGNORECASE | re.DOTALL)
                        if m:
                            func_name_cand = m.group(1).strip()
                            # Allow matching even if the schema isn't found so that the error handler can catch hallucinations
                            match = m
                            break
                    if match:
                        func_name = match.group(1).strip()
                        args_raw = match.group(2).strip()
                        try:
                            schema = next((s['function'] for s in tool_schemas if s['function']['name'] == func_name), None)
                            props = schema.get('parameters', {}).get('properties', {}) if schema else {}
                            if args_raw.startswith('{') and args_raw.endswith('}'):
                                try:
                                    parsed_json = json.loads(args_raw)
                                    common_keys = ['path', 'file', 'url', 'query', 'arg', 'text', 'file_path']
                                    if len(props) == 1:
                                        first_key = list(props.keys())[0]
                                        if first_key in parsed_json:
                                            parsed_args = {first_key: parsed_json[first_key]}
                                        else:
                                            extracted_val = next((parsed_json[k] for k in common_keys if k in parsed_json), None)
                                            if extracted_val is not None:
                                                parsed_args = {first_key: extracted_val}
                                            else:
                                                parsed_args = parsed_json
                                    else:
                                        parsed_args = parsed_json
                                except json.JSONDecodeError:
                                    parsed_args = {}
                            elif props:
                                first_key = list(props.keys())[0]
                                parsed_args = {first_key: args_raw}
                            else:
                                parsed_args = {}
                            tool_calls.append({'function': {'name': func_name, 'arguments': parsed_args}})
                            content = str(content).replace(match.group(0), '')
                            response_msg['content'] = content
                        except Exception as e:
                            logger.warning(f'Failed to parse universal plaintext tool call: {e}')
                    if not match and (not tool_calls) and tool_schemas and (len(executed_signatures) == 0):
                        found_tool_name = None
                        for schema in tool_schemas:
                            t_name = schema.get('function', {}).get('name')
                            if t_name and t_name in str(content):
                                found_tool_name = t_name
                                break
                        if found_tool_name:
                            path_ext_pattern = '(/home/[/\\w\\-.]+|~/[/\\w\\-.]+|\\./[/\\w\\-.]+|/?[\\w\\-./]+\\.(?:pdf|txt|py|sh|json|csv)\\b)'
                            arg_match = re.search(path_ext_pattern, str(content), flags=re.IGNORECASE)
                            if not arg_match:
                                arg_match = re.search('["\\\']([^"\\\']+)["\\\']', str(content))
                            if arg_match:
                                extracted_arg = arg_match.group(1) if arg_match.groups() else arg_match.group(0)
                                try:
                                    schema = next((s['function'] for s in tool_schemas if s['function']['name'] == found_tool_name))
                                    props = schema.get('parameters', {}).get('properties', {})
                                    if props:
                                        first_key = list(props.keys())[0]
                                        parsed_args = {first_key: extracted_arg.strip()}
                                    else:
                                        parsed_args = {}
                                    tool_calls.append({'function': {'name': found_tool_name, 'arguments': parsed_args}})
                                    content = str(content).replace(found_tool_name, '').replace(extracted_arg, '')
                                    response_msg['content'] = content
                                except Exception as e:
                                    logger.warning(f'Failed to parse co-occurrence tool call: {e}')
                if intent in ('orchestration', 'code') and tool_schemas and self._is_disallowed_action_greeting(content):
                    if tool_calls:
                        content = ''
                        response_msg['content'] = ''
                    else:
                        override_prompt = DIRECT_ACTION_MODE_GUARD + ' Your previous response was rejected because it was an introductory preamble. Issue the required native tool call now.'
                        self._log('Rejected introductory model preamble on Direct Action Mode turn.', steps)
                        continue
                if content:
                    content_str = str(content)
                    content_str = re.sub('<think>[\\s\\S]*?(?:</think>|$)', '', content_str, flags=re.IGNORECASE)
                    content_str = content_str.replace('</think>', '').replace('<think>', '').strip()
                    content_str = re.sub('^(assistant|role:\\s*assistant):?\\s*\\n+', '', content_str, flags=re.IGNORECASE).strip()
                    content_str = re.sub('^(?:Final Answer:|Please try again\\.)\\s*', '', content_str, flags=re.IGNORECASE).strip()
                    content_str = re.sub('<\\|.*?\\|>', '', content_str).strip()
                    content_str = re.sub('```json.*?```', '', content_str, flags=re.DOTALL).strip()
                    content_str = re.sub('\\[[^\\]]*?(?:extracted|processed|opened|completed)[^\\]]*?\\]', '', content_str, flags=re.IGNORECASE).strip()
                    wrapper_match = re.search('assistant\\s*\\{\\s*"answer"\\s*:\\s*"(.*?)"\\s*\\}', content_str, flags=re.IGNORECASE | re.DOTALL)
                    if wrapper_match:
                        content_str = wrapper_match.group(1).strip()
                    content_str = re.sub('^(?:invoke|tool_call|PDF Content|Result):?\\s*', '', content_str, flags=re.IGNORECASE).strip()
                    if content_str:
                        accumulated_response += content_str + '\n\n'
                if tool_calls and use_tools:
                    self._persist_step(session_id, 'reasoning', response_msg)
                    state = AgentState.ACT
                    pending_calls = tool_calls
                    assistant_msg = response_msg
                else:
                    if accumulated_response.strip():
                        final_response = accumulated_response.strip()
                    elif observations:
                        final_response = self._format_latest_observation_response(observations)
                    else:
                        logger.warning('Model returned empty response on conversational turn.')
                        final_response = ' [!] The model returned an empty response. Try rephrasing or typing /help.'
                    if intent == 'chat' and self._is_duplicate_assistant_response(final_response):
                        logger.warning('Echo Pruning: Dropped duplicate assistant response from history buffer.')
                        retry_response, retry_message = self._retry_pruned_chat_response(task=task, plan=plan, observations=observations, session_id=session_id, timeout=time_left)
                        final_response = retry_response or CHAT_ECHO_RETRY_FALLBACK
                        accumulated_response = final_response
                        if retry_message is not None:
                            self._persist_step(session_id, 'reasoning', retry_message)
                    else:
                        self._persist_step(session_id, 'reasoning', response_msg)
                    state = AgentState.REFLECT
            elif state == AgentState.ACT:
                executed_tool_ids_this_round = set()
                file_mutators = 0
                has_delete = False
                for tc in pending_calls:
                    func = tc.get('function', {}) if isinstance(tc, dict) else {}
                    t_name = func.get('name') or tc.get('name') or ''
                    if t_name in ('write_file', 'replace_file_content', 'multi_replace_file_content'):
                        file_mutators += 1
                    if t_name == 'delete_file':
                        has_delete = True
                is_high_risk = has_delete or file_mutators > 3
                if is_high_risk:
                    self._log(f'ACT: High-risk batch detected ({file_mutators} mutators, delete={has_delete}). Triggering Swarm Consensus.', steps)
                    consensus_engine = ConsensusEngine(self._bus if hasattr(self, '_bus') else getattr(self, 'bus', None))
                    context_summary = json.dumps([{'role': msg['role'], 'content': msg['content'][:200]} for msg in self._chat_history[-3:]])
                    consensus_reached = self._run_coro_sync(consensus_engine.run_debate(task=task, context=context_summary, pending_tools=pending_calls))
                    if not consensus_reached:
                        self._log('ACT: Swarm Consensus REJECTED the operation.', steps)
                        for tc in pending_calls:
                            func = tc.get('function', {}) if isinstance(tc, dict) else {}
                            tool_name = func.get('name') or tc.get('name') or 'unknown'
                            arguments = func.get('arguments', tc.get('arguments', {}))
                            observations.append(self._structured_tool_result(tool_name, arguments, {'error': 'Swarm Consensus rejected the proposed execution plan. Revise your approach.'}, False))
                        state = AgentState.OBSERVE
                        continue
                    self._log('ACT: Swarm Consensus APPROVED.', steps)
                for tc in pending_calls:
                    try:
                        tool_name, arguments, tc_id = self._normalize_tool_call(tc)
                    except ValueError as exc:
                        tool_name = tc.get('function', {}).get('name') or tc.get('name') or 'unknown'
                        observations.append(self._structured_tool_result(tool_name, tc, {'error': f'Malformed tool arguments JSON: {exc}. Please fix the syntax.'}, False))
                        continue
                    sig = tc_id or hashlib.md5(f'{tool_name}:{json.dumps(arguments, sort_keys=True, default=str)}'.encode()).hexdigest()
                    dedup_sig = f'{tool_name}:{str(sorted(arguments.items()))}'
                    self._tool_call_history.append(sig)
                    if dedup_sig in executed_signatures:
                        if self._tool_call_history.count(sig) >= 3:
                            override_prompt = 'You are repeating yourself exactly. Abort current strategy and re-evaluate. You MUST output a plain-text final answer or ask for clarification.'
                            force_text_response = True
                        else:
                            override_prompt = f"[System Notice] Tool '{tool_name}' with these arguments was already executed this turn. Use the existing output above to formulate your final response."
                        result = self._structured_tool_result(tool_name, arguments, {'error': override_prompt}, False)
                        observations.append(result)
                        self._persist_step(session_id, 'tool_result', result)
                        self._log(f'ACT {tool_name}: BLOCKED BY LOOP BREAKER.', steps)
                        continue
                    if txn.should_snapshot(tool_name):
                        for arg_key in ('path', 'file', 'filename', 'dest', 'destination'):
                            target_path = arguments.get(arg_key)
                            if target_path:
                                try:
                                    txn.snapshot(target_path)
                                except StagingCapExceeded as cap_err:
                                    observations.append(self._structured_tool_result(tool_name, arguments, {'error': f'Transaction staging cap exceeded: {cap_err}'}, False))
                                    self._log(f'ACT {tool_name}: staging cap exceeded, skipping tool.', steps)
                                    break
                                except Exception as snap_err:
                                    logger.warning("Snapshot failed for %s arg '%s': %s", tool_name, arg_key, snap_err)
                    if sig in executed_tool_ids_this_round:
                        result = self._structured_tool_result(tool_name, arguments, {'error': 'Duplicate tool call skipped for this inference step.'}, False)
                    else:
                        executed_tool_ids_this_round.add(sig)
                        executed_signatures.add(dedup_sig)
                        result = self._execute_tool(tool_name, arguments)
                    observations.append(result)
                    self._persist_step(session_id, 'tool_result', result)
                    self._log(f"ACT {tool_name}: success={result.get('success')}", steps)
                state = AgentState.OBSERVE
            elif state == AgentState.OBSERVE:
                self._log('OBSERVE: incorporated latest tool results', steps)
                self._persist_step(session_id, 'observation', {'observations': observations[-3:]})
                state = AgentState.REFLECT
            elif state == AgentState.REFLECT:
                reflection = self._reflect(task, plan, observations, final_response)
                self._persist_step(session_id, 'reflection', reflection)
                if reflection.get('complete') or final_response:
                    if final_response:
                        pass
                    elif reflection.get('answer'):
                        final_response = str(reflection.get('answer'))
                    elif accumulated_response.strip():
                        final_response = accumulated_response.strip()
                    elif observations:
                        final_response = self._format_latest_observation_response(observations)
                    else:
                        logger.warning('Model returned empty response on conversational turn.')
                        final_response = ' [!] The model returned an empty response. Try rephrasing or typing /help.'
                    state = AgentState.EXIT
                else:
                    plan.current_step = min(plan.current_step + 1, max(len(plan.steps) - 1, 0))
                    if len(observations) > 0 and (not override_prompt):
                        override_prompt = '[System Notice: Tool execution complete. You MUST now write a plain-English summary of these findings for the user. Do not leave your response blank.]'
                    state = AgentState.THINK
                self._save_plan(session_id, plan)
            round_duration_ms = (time.perf_counter() - round_start_time) * 1000
            self._emit('loop.cycle', {'session_id': session_id, 'round': rounds, 'state': state.value if hasattr(state, 'value') else str(state), 'duration_ms': round_duration_ms, 'queue_depth': len(pending_calls) if state == AgentState.ACT else 0})
        if not final_response:
            final_response = 'Task processing reached maximum rounds. Review tool results for partial progress.'
            self._emit('plan.failed', {'reason': 'max_rounds', 'step': rounds, 'total_steps': MAX_TOOL_ROUNDS})
            txn.rollback()
        else:
            txn.commit()
        is_empty_warning = '[!] The model returned an empty response' in final_response
        is_echo = self._is_duplicate_assistant_response(final_response)
        if is_echo:
            logger.warning('Echo Pruning: Dropped duplicate assistant response from history buffer.')
            final_response = CHAT_ECHO_RETRY_FALLBACK if intent == 'chat' else PRUNED_ECHO_INDICATOR
        if final_response.strip() and (not is_empty_warning) and (not is_echo):
            self._chat_history = (self._chat_history + [{'role': 'user', 'content': task}, {'role': 'assistant', 'content': final_response}])[-20:]
        if self._context_manager.should_summarize(self._chat_history):
            self._persist_summary(session_id, self._chat_history)
        self._persist_step(session_id, 'assistant', {'response': final_response})
        self._emit('orchestrator.task.completed', {'task': task, 'success': True, 'rounds': rounds, 'session_id': session_id})
        return AgentResult(True, output={'response': final_response, 'tool_results': observations, 'rounds': rounds, 'session_id': session_id, 'plan': asdict(plan)}, steps_taken=steps)

    def _build_messages(self, task: str, plan: Plan, observations: List[Dict[str, Any]], session_id: str, override_prompt: Optional[str]=None, intent: str='orchestration') -> List[Dict[str, Any]]:
        """Auto-generated docstring.

Args:
    task: Argument.
    plan: Argument.
    observations: Argument.
    session_id: Argument.
    override_prompt: Argument.
    intent: Argument.

Returns:
    Return value.
"""
        mem_start_time = time.perf_counter()
        memories = self._retrieve_relevant_memory(task, session_id, top_k=6)
        persisted_summaries = self._retrieve_summaries(session_id)
        mem_duration_ms = (time.perf_counter() - mem_start_time) * 1000
        self._emit('memory.retrieved', {'session_id': session_id, 'latency_ms': mem_duration_ms, 'results_count': len(memories) + len(persisted_summaries)})
        from axiom.config import get_config
        config = get_config()
        tools_loaded = False
        if intent != 'chat' and self.registry and hasattr(self.registry, 'list_tools'):
            try:
                tools_loaded = bool(self.registry.list_tools())
            except Exception:
                logger.debug('Unable to determine whether action tools are loaded.', exc_info=True)
        system_persona = "You are AXIOM, a local-first AI Operating System and developer assistant for Linux. You have access to native tools for file management, terminal execution, system monitoring, vision analysis, and sandboxed code execution. When asked about your capabilities, summarize your active tools and OS integration rather than speaking as a generic text assistant."

        if intent == 'chat':
            base_prompt = system_persona + ' Be concise, helpful, and conversational. Do not list your tools unless explicitly asked.'
        else:
            base_prompt = (DIRECT_ACTION_MODE_GUARD + '\n\n' if tools_loaded else '') + system_persona + "\n1. Your sole purpose is to execute requested tasks using the provided tools.\n2. NEVER output your internal reasoning, thought process, or status logs in the Final Answer.\n3. If a tool call is required, invoke it natively and silently. DO NOT output raw JSON blocks in your text response.\n4. If no tool is required, provide ONLY the direct response to the user.\n5. If you must plan, keep it in an internal-only scratchpad (if implemented), but do not send it to the user interface.\n6. You MUST invoke tools using the native structured tool-call API whenever possible. If outputting text tool calls, strictly use registered tool names.\n7. CRITICAL RULE: You are strictly FORBIDDEN from claiming to have performed an action (opening a file, reading a document, executing a script) unless you have actually emitted a tool call and received the verified [System Observation]. DO NOT roleplay, simulate, or hallucinate tool execution in conversational prose. If a tool is not available, state explicitly that you cannot perform the action.\n8. CRITICAL Temporal Rule: You must respond ONLY to the user's latest (most recent) message at the very bottom of the prompt. Use older conversation history solely for context and reference. NEVER ignore the latest prompt to answer old, ignored, or previously addressed questions from earlier turns.\nCONSTRAINTS:\n- NO verbose planning logs.\n- STRIKE the 'Final Answer:' header from your output; just provide the content.\n9. [MULTIMODAL PERCEPTION] If the user refers to 'this window', 'my screen', 'look at this', or asks to diagnose a visual issue, you MUST use the 'capture_screen_context' tool."
        try:
            from axiom.perception.watcher import ActiveWindowContext
            active_win = ActiveWindowContext.get_active_window_title()
            base_prompt += f"\n\n[System Context: User is currently looking at active window: '{active_win}']"
        except ImportError:
            pass
        if config.behavior and config.behavior.profile in ('tech_beginner', 'casual'):
            base_prompt += ' The user is a beginner or casual user. You MUST prioritize safe, read-only assistive tools like SafeFileSearchTool, FileOpenerTool, and AppLauncherTool over raw Bash or FileEdit tools. Explain things simply.'
        if intent != 'chat' and hasattr(self, 'registry') and self.registry:
            try:
                tools = self.registry.list_tools() if hasattr(self.registry, 'list_tools') else {}
                if tools:
                    capabilities = []
                    for t_name, t_obj in tools.items():
                        desc = getattr(t_obj, 'description', 'No description available')
                        capabilities.append(f'{t_name} ({desc})')
                    if capabilities:
                        base_prompt += f"\n\n[Available System Capabilities]: You have access to the following tools: {', '.join(capabilities)}."
                        base_prompt += '\nIf the user asks what you can do or what tools you have, explicitly summarize your [Available System Capabilities] in plain, friendly English.'
            except Exception as e:
                self._log(f'Failed to inject tool capabilities: {e}', [])
        episodic_summaries = []
        if hasattr(self, '_memory_store') and self._memory_store:
            try:
                summary_records = self._memory_store.search(['episodic_summary'])
                episodic_summaries = [rec.get('value') or rec.get('value_json') for rec in summary_records[:5]]
            except Exception as e:
                self._log(f'Failed to fetch episodic summaries: {e}', [])
        system_messages = [{'role': 'system', 'content': base_prompt}, {'role': 'system', 'content': json.dumps({'plan': asdict(plan), 'persisted_summaries': persisted_summaries, 'episodic_knowledge': episodic_summaries}, default=str)}]
        if override_prompt:
            system_messages.append({'role': 'system', 'content': override_prompt})
        if intent != 'chat':
            task = f'[Current Task - IGNORE ALL PREVIOUS UNANSWERED OR INCOMPLETE TOPICS AND EXECUTE ONLY THIS REQUEST]: {task}'
        messages = self._context_manager.build_context_window(system_messages=system_messages, chat_history=self._chat_history, current_task=task, retrieved_memories=memories, observations=observations)
        budget = self._context_manager.max_tokens
        used_tokens = estimate_messages_tokens(messages)
        if used_tokens > 0.85 * budget:
            self._log('Context > 85% utilized. Forcing adaptive memory compression.', [])
            self._persist_summary(session_id, self._chat_history)
            obs_tokens = estimate_messages_tokens([{'role': 'system', 'content': json.dumps(observations, default=str)}])
            if obs_tokens > 0.5 * budget:
                observations = [{'error': 'Output truncated due to context limits. Too much data returned.'}]
                messages = self._context_manager.build_context_window(system_messages=system_messages, chat_history=self._chat_history, current_task=task, retrieved_memories=memories, observations=observations)
        return messages

    def _call_llm(self, messages: List[Dict[str, Any]], tool_schemas: List[Dict[str, Any]], timeout: Optional[float]=None, temperature: Optional[float]=None) -> Dict[str, Any]:
        """Auto-generated docstring.

Args:
    messages: Argument.
    tool_schemas: Argument.
    timeout: Argument.
    temperature: Argument.

Returns:
    Return value.
"""
        last_exc = None
        for attempt in range(LLM_RETRIES):
            try:
                if tool_schemas and hasattr(self._llm, 'chat_with_tools'):
                    kwargs = {'timeout': timeout} if timeout else {}
                    if temperature is not None:
                        kwargs['temperature'] = temperature
                    msg = self._llm.chat_with_tools(messages, tool_schemas, **kwargs)
                    response = msg if isinstance(msg, dict) else {'role': 'assistant', 'content': str(msg)}
                else:
                    kwargs = {'timeout': timeout} if timeout else {}
                    if temperature is not None:
                        kwargs['temperature'] = temperature
                    content = self._llm.chat(messages, **kwargs)
                    response = {'role': 'assistant', 'content': content or ''}
                
                content_str = response.get('content', '')
                tool_calls = response.get('tool_calls', [])
                if not content_str.strip() and not tool_calls:
                    current_model = getattr(getattr(self._llm, 'config', None), 'model', 'unknown')
                    logger.warning(f"[Auto-Recovery] Model {current_model} returned empty response. Retrying turn with reliable fallback (qwen3:8b)...")
                    if hasattr(self._llm, 'config'):
                        self._llm.config.model = 'ollama/qwen3:8b'
                    continue
                    
                return response
            except Exception as exc:
                last_exc = exc
                time.sleep(min(2 ** attempt, 8) * 0.25)
        return {'role': 'assistant', 'content': f'LLM call failed after retries: {last_exc}'}

    def _normalize_tool_call(self, tc: Dict[str, Any]) -> tuple[str, Dict[str, Any], str]:
        """Auto-generated docstring.

Args:
    tc: Argument.

Returns:
    Return value.
"""
        func = tc.get('function', {}) if isinstance(tc, dict) else {}
        tool_name = func.get('name') or tc.get('name') or 'unknown'
        arguments = func.get('arguments', tc.get('arguments', {}))
        if isinstance(arguments, str):
            arguments = self._safe_json_obj(arguments)
        if not isinstance(arguments, dict):
            arguments = {'input': arguments}
        tc_id = tc.get('id') or f"call_{hashlib.md5(f'{tool_name}:{json.dumps(arguments, sort_keys=True, default=str)}'.encode()).hexdigest()}"
        return (tool_name, arguments, tc_id)

    def _safe_json_obj(self, text: str) -> Dict[str, Any]:
        """Auto-generated docstring.

Args:
    text: Argument.

Returns:
    Return value.
"""
        raw = text.strip()
        fence = re.search('```(?:json)?\\s*(.*?)```', raw, flags=re.DOTALL | re.IGNORECASE)
        if fence:
            raw = fence.group(1).strip()
        is_json_like = raw.startswith('{') or fence is not None
        if not raw.startswith('{'):
            match = re.search('\\{.*\\}', raw, flags=re.DOTALL)
            raw = match.group(0) if match else raw
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {'input': parsed}
        except Exception as e:
            if is_json_like:
                raise ValueError(str(e))
            return {'input': text}

    def _create_plan(self, task: str) -> Plan:
        """Auto-generated docstring.

Args:
    task: Argument.

Returns:
    Return value.
"""
        return Plan(objective=task, steps=['Understand the objective', 'Use tools if needed', 'Synthesize final answer'], current_step=0)

    def _reflect(self, task: str, plan: Plan, observations: List[Dict[str, Any]], final_response: str) -> Dict[str, Any]:
        """Auto-generated docstring.

Args:
    task: Argument.
    plan: Argument.
    observations: Argument.
    final_response: Argument.

Returns:
    Return value.
"""
        if final_response:
            return {'complete': True, 'answer': final_response, 'reason': 'LLM produced final response'}
        if observations and (not observations[-1].get('success', False)):
            return {'complete': False, 'reason': 'Latest tool failed, another plan step may be needed'}
        if observations and plan.current_step >= len(plan.steps) - 1:
            return {'complete': False, 'reason': 'Need synthesis after tool observations'}
        return {'complete': False, 'reason': 'Continue plan'}

    def _get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Auto-generated docstring.


Returns:
    Return value.
"""
        if self.registry and hasattr(self.registry, 'get_schemas'):
            return self.registry.get_schemas()
        schemas: List[Dict[str, Any]] = []
        tools = self.registry.list_tools() if self.registry and hasattr(self.registry, 'list_tools') else {}
        for tool_id, tool in tools.items():
            tool_schema = getattr(tool, 'schema', None)
            if isinstance(tool_schema, dict):
                schemas.append({'type': 'function', 'function': {'name': tool_id, 'description': getattr(tool, 'description', tool_id), 'parameters': tool_schema}})
        return schemas

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Auto-generated docstring.

Args:
    tool_name: Argument.
    arguments: Argument.

Returns:
    Return value.
"""
        start_time = time.perf_counter()

        def _scrub_jargon(err_msg: str) -> str:
            """Auto-generated docstring.

Args:
    err_msg: Argument.

Returns:
    Return value.
"""
            if not err_msg:
                return err_msg
            err_str = str(err_msg)
            if 'FileNotFoundError' in err_str or 'No such file' in err_str:
                return "I couldn't find that file. Are you sure the name and path are correct?"
            if 'PermissionError' in err_str or 'Permission denied' in err_str:
                return "I don't have permission to access that file or folder. You might need to change its permissions."
            return err_str
        try:
            if self.registry and hasattr(self.registry, 'execute'):
                tool_result = self.registry.execute(tool_name, **arguments)
                raw_error = getattr(tool_result, 'error', None)
                error = _scrub_jargon(raw_error) if isinstance(raw_error, str) else None
                payload = {'output': getattr(tool_result, 'output', None), 'error': error}
                result_dict = self._structured_tool_result(tool_name, arguments, payload, bool(getattr(tool_result, 'success', False)))
            else:
                tools = self.registry.list_tools() if self.registry and hasattr(self.registry, 'list_tools') else {}
                tool = tools.get(tool_name) or next((t for t in tools.values() if getattr(t, 'name', None) == tool_name), None)
                if not tool:
                    result_dict = self._structured_tool_result(tool_name, arguments, {'error': f'Tool not found: {tool_name}'}, False)
                else:
                    result = tool.execute(arguments)
                    if asyncio.iscoroutine(result):
                        result = self._run_coro_sync(result)
                    if isinstance(result, dict) and {'tool', 'arguments', 'result', 'success'}.issubset(result.keys()):
                        if 'error' in result.get('result', {}):
                            result['result']['error'] = _scrub_jargon(result['result']['error'])
                        result_dict = result
                    else:
                        raw_err = getattr(result, 'error', None)
                        payload = {'output': getattr(result, 'output', result), 'error': _scrub_jargon(raw_err) if isinstance(raw_err, str) else raw_err}
                        result_dict = self._structured_tool_result(tool_name, arguments, payload, bool(getattr(result, 'success', True)))
        except Exception as exc:
            result_dict = self._structured_tool_result(tool_name, arguments, {'error': _scrub_jargon(str(exc))}, False)
        duration_ms = (time.perf_counter() - start_time) * 1000
        self._emit('tool.executed', {'tool_name': tool_name, 'arguments': arguments, 'duration_ms': duration_ms, 'success': result_dict.get('success', False), 'error': result_dict.get('result', {}).get('error', None)})
        if tool_name == 'safe_file_search':
            results = result_dict.get('result', {}).get('output', [])
            self._emit('assist.search.completed', {'query': arguments.get('query'), 'results_count': len(results) if isinstance(results, list) else 0})
        elif tool_name == 'app_launcher':
            self._emit('assist.app.launched', {'app_name': arguments.get('app_name')})
        elif tool_name == 'file_opener':
            self._emit('assist.file.opened', {'file_path': arguments.get('file_path')})
        return result_dict

    def _format_observation_response(self, observation: Dict[str, Any]) -> str:
        """Render a tool result without masking empty document extraction failures."""
        tool_name = str(observation.get('tool') or 'unknown')
        arguments: dict[Any, Any] = observation.get('arguments') if isinstance(observation.get('arguments'), dict) else {}
        result: dict[Any, Any] = observation.get('result') if isinstance(observation.get('result'), dict) else {}
        error = result.get('error')
        output = result.get('output')
        if error:
            text = str(error).strip()
        else:
            text = output.get('content') if isinstance(output, dict) and 'content' in output else output
            if text is None or (isinstance(text, str) and (not text.strip())):
                if tool_name in {'read_document_content', 'file_read'}:
                    file_path = arguments.get('file_path') or arguments.get('path') or arguments.get('file') or '<unknown file>'
                    text = DOCUMENT_EXTRACTION_NOTICE.format(file_path=file_path)
                else:
                    text = f"[Tool Result Notice]: '{tool_name}' completed without a displayable result."
            elif not isinstance(text, str):
                text = json.dumps(text, default=str)
        return f'[Observation Result]:\n\n{text}'

    def _format_latest_observation_response(self, observations: List[Dict[str, Any]]) -> str:
        """Render the latest user-displayable observation, not internal control flow."""
        for observation in reversed(observations):
            if not self._is_internal_observation_notice(observation):
                return self._format_observation_response(observation)
        return '[Tool Result Notice]: No user-displayable tool result was produced.'

    @staticmethod
    def _is_internal_observation_notice(observation: Dict[str, Any]) -> bool:
        """Auto-generated docstring.

Args:
    observation: Argument.

Returns:
    Return value.
"""
        result = observation.get('result') if isinstance(observation, dict) else None
        if not isinstance(result, dict):
            return False
        candidates = [result.get('error')]
        output = result.get('output')
        if isinstance(output, dict):
            candidates.extend((output.get('content'), output.get('error'), output.get('message')))
        else:
            candidates.append(output)
        return any((isinstance(value, str) and value.lstrip().lower().startswith(INTERNAL_OBSERVATION_PREFIXES) for value in candidates))

    def _retry_pruned_chat_response(self, task: str, plan: Plan, observations: List[Dict[str, Any]], session_id: str, timeout: Optional[float]) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Make one diversified retry after suppressing a conversational echo."""
        try:
            messages = self._build_messages(task, plan, observations, session_id, override_prompt=CHAT_ECHO_RETRY_PROMPT, intent='chat')
            retry_message = self._call_llm(messages, [], timeout=timeout, temperature=0.4)
            content = self._clean_retry_content(retry_message.get('content'))
            if content and (not self._is_duplicate_assistant_response(content)):
                return (content, retry_message)
        except Exception as exc:
            logger.warning('Echo-pruning retry failed: %s', exc)
        return (None, None)

    @staticmethod
    def _clean_retry_content(content: Any) -> str:
        """Auto-generated docstring.

Args:
    content: Argument.

Returns:
    Return value.
"""
        if not content:
            return ''
        cleaned = str(content)
        cleaned = re.sub('<think>[\\s\\S]*?(?:</think>|$)', '', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.replace('</think>', '').replace('<think>', '').strip()
        cleaned = re.sub('^(assistant|role:\\s*assistant):?\\s*\\n+', '', cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub('^(?:Final Answer:|Please try again\\.)\\s*', '', cleaned, flags=re.IGNORECASE).strip()
        return cleaned

    def _is_duplicate_assistant_response(self, response: Any) -> bool:
        """Auto-generated docstring.

Args:
    response: Argument.

Returns:
    Return value.
"""
        if not isinstance(response, str) or not response.strip():
            return False
        if not self._chat_history or self._chat_history[-1].get('role') != 'assistant':
            return False
        last_message = str(self._chat_history[-1].get('content', '')).strip()
        candidate = response.strip()
        return bool(last_message and (candidate == last_message or candidate in last_message))

    @staticmethod
    def _is_disallowed_action_greeting(content: Any) -> bool:
        """Auto-generated docstring.

Args:
    content: Argument.

Returns:
    Return value.
"""
        if not isinstance(content, str):
            return False
        normalized = ' '.join(content.lower().split())
        return any((phrase in normalized for phrase in ('i am axiom', "i'm axiom", 'i’m axiom', 'here is what i can do', 'how can i assist you today')))

    def _structured_tool_result(self, tool: str, arguments: Dict[str, Any], result: Dict[str, Any], success: bool) -> Dict[str, Any]:
        """Auto-generated docstring.

Args:
    tool: Argument.
    arguments: Argument.
    result: Argument.
    success: Argument.

Returns:
    Return value.
"""
        return {'tool': tool, 'arguments': arguments if isinstance(arguments, dict) else {'input': arguments}, 'result': result if isinstance(result, dict) else {'output': result}, 'success': bool(success)}

    def _run_coro_sync(self, coro):
        """Auto-generated docstring.

Args:
    coro: Argument.

Returns:
    Return value.
"""
        from axiom.core.async_bridge import run_sync
        return run_sync(coro)

    def _persist_step(self, session_id: str, kind: str, payload: Any) -> None:
        """Auto-generated docstring.

Args:
    session_id: Argument.
    kind: Argument.
    payload: Argument.

Returns:
    Return value.
"""
        if not self.memory:
            return
        try:
            key = f'session:{session_id}:step:{time.time_ns()}:{kind}'
            if hasattr(self.memory, 'set'):
                self.memory.set(key, {'kind': kind, 'payload': payload, 'timestamp': time.time()}, tags=['session', session_id, kind])
            if hasattr(self.memory, 'log_event'):
                self.memory.log_event(f'orchestrator.{kind}', {'session_id': session_id, 'payload': payload}, source='orchestrator')
        except Exception as exc:
            logger.debug('Failed to persist step: %s', exc)

    def _persist_summary(self, session_id: str, chat_history: List[Dict[str, Any]]) -> None:
        """Persist a summary of older conversation turns to memory."""
        if not self.memory:
            return
        older_turns = self._context_manager.get_turns_for_summary(chat_history)
        if not older_turns:
            return
        summary = self._context_manager._summarize_turns(older_turns)
        if not summary:
            return
        try:
            key = f'session:{session_id}:summary:{time.time_ns()}'
            if hasattr(self.memory, 'set'):
                self.memory.set(key, {'summary': summary['content'], 'turns_covered': len(older_turns)}, tags=['session', session_id, 'summary'])
        except Exception as exc:
            logger.debug('Failed to persist summary: %s', exc)

    def _retrieve_summaries(self, session_id: str, limit: int=3) -> List[str]:
        """Retrieve persisted conversation summaries for this session."""
        if not self.memory or not hasattr(self.memory, 'search'):
            return []
        try:
            rows = self.memory.search([session_id, 'summary'])
            summaries = []
            for row in rows:
                value = row.get('value', {})
                if isinstance(value, dict) and 'summary' in value:
                    summaries.append(value['summary'])
            return summaries[-limit:]
        except Exception:
            return []

    def _retrieve_relevant_memory(self, task: str, session_id: str, top_k: int=5) -> List[Dict[str, Any]]:
        """Auto-generated docstring.

Args:
    task: Argument.
    session_id: Argument.
    top_k: Argument.

Returns:
    Return value.
"""
        if not self.memory or not hasattr(self.memory, 'search'):
            return []
        terms = [w.lower() for w in re.findall('[a-zA-Z0-9_]{4,}', task)][:12]
        try:
            rows = self.memory.search([session_id]) + self.memory.search(['session'])
        except Exception:
            return []
        scored = []
        for row in rows:
            text = json.dumps(row.get('value', row), default=str).lower()
            score = sum((1 for term in terms if term in text))
            if score:
                scored.append((score, row))
        return [row for _, row in sorted(scored, key=lambda x: x[0], reverse=True)[:top_k]]

    def _save_plan(self, session_id: str, plan: Plan) -> None:
        """Auto-generated docstring.

Args:
    session_id: Argument.
    plan: Argument.

Returns:
    Return value.
"""
        if self.memory and hasattr(self.memory, 'set'):
            try:
                self.memory.set(f'session:{session_id}:plan', asdict(plan), tags=['session', session_id, 'plan'])
            except Exception:
                pass

    def _load_plan(self, session_id: str) -> Optional[Plan]:
        """Auto-generated docstring.

Args:
    session_id: Argument.

Returns:
    Return value.
"""
        if self.memory and hasattr(self.memory, 'get'):
            try:
                data = self.memory.get(f'session:{session_id}:plan')
                if isinstance(data, dict):
                    return Plan(**data)
            except Exception:
                return None
        return None

    def _prefix_route(self, task: str, steps: List[str]) -> AgentResult:
        """Auto-generated docstring.

Args:
    task: Argument.
    steps: Argument.

Returns:
    Return value.
"""
        prefix, subtask = task.split(':', 1) if ':' in task else (None, task)
        prefix = prefix.strip() if prefix else None
        subtask = subtask.strip()
        agent = self._agents.get('echo_agent') if prefix == 'echo' else None
        if agent is not None:
            self._log(f'Routing to agent: {agent.name}', steps)
            result = agent.run(subtask)
            return AgentResult(getattr(result, 'success', True), output=getattr(result, 'output', None), error=getattr(result, 'error', None), steps_taken=steps + getattr(result, 'steps_taken', []))
        return AgentResult(False, error=f'No agent matched for: {task}', steps_taken=steps)
