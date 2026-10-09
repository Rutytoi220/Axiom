"""Offline evaluation harness executing tasks with mocked streams and isolated sandboxes."""

from __future__ import annotations

import asyncio
import inspect
import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from axiom.agents.native_orchestrator import NativeOrchestrator
from axiom.db.memory import MemoryStore
from axiom.eval.metrics import EvalStatus, TaskResult
from axiom.eval.provider import MockTurn
from axiom.eval.task import EvalContext, EvalTask
from axiom.eval.types import EvaluationResult, ResultStatus, ValidationResult
from axiom.tools.core import ToolResult


class EvalHarness:
    """100% offline, deterministic orchestration evaluation harness."""

    async def run_task(
        self,
        task: EvalTask,
        mock_responses: Optional[List[Dict[str, Any]]] = None,
        mock_stream_fn: Optional[Callable[[dict], Any]] = None,
        custom_tools: Optional[Dict[str, Callable[..., Any]]] = None,
    ) -> TaskResult:
        """Execute an EvalTask inside an isolated workspace and validate observable state."""
        start_time = time.perf_counter()

        temp_dir = Path(tempfile.mkdtemp(prefix=f"axiom_eval_{task.task_id}_")).resolve()
        db_path = temp_dir / "test_eval.db"

        memory_store = MemoryStore(db_path=str(db_path))

        context = EvalContext(
            task=task,
            workspace_dir=temp_dir,
            db_path=db_path,
            memory_store=memory_store,
        )

        status: EvalStatus = EvalStatus.UNVERIFIED
        status_message: str = ""
        failure_category: Optional[str] = None
        tool_names_called: List[str] = []
        estimated_token_count: int = 0
        step_counter: int = 0

        # Merge tool handlers
        tools_map = dict(task.custom_tools or task.fake_tools or {})
        if custom_tools:
            tools_map.update(custom_tools)

        # Scoped tool executor
        async def scoped_tool_executor(name: str, args: Any) -> Any:
            tool_names_called.append(name)
            if task.allowed_tools is not None and name not in task.allowed_tools:
                err_env = ToolResult(
                    success=False,
                    error=f"Security Violation: Tool '{name}' is not in allowed_tools {task.allowed_tools}",
                    remedy_hint=f"Use allowed tools: {task.allowed_tools}",
                    allowed_actions=list(task.allowed_tools),
                ).to_dict(tool=name, arguments=args if isinstance(args, dict) else {})
                context.record_tool_invocation(name, args if isinstance(args, dict) else {}, err_env)
                return err_env

            handler = tools_map.get(name)
            if handler is None:
                err_env = ToolResult(
                    success=False,
                    error=f"Tool '{name}' has no registered implementation.",
                ).to_dict(tool=name, arguments=args if isinstance(args, dict) else {})
                context.record_tool_invocation(name, args if isinstance(args, dict) else {}, err_env)
                return err_env

            call_kwargs = dict(args) if isinstance(args, dict) else {}
            sig = inspect.signature(handler)
            if "context" in sig.parameters and "context" not in call_kwargs:
                call_kwargs["context"] = context
            if "workspace" in sig.parameters and "workspace" not in call_kwargs:
                call_kwargs["workspace"] = temp_dir
            if "db_path" in sig.parameters and "db_path" not in call_kwargs:
                call_kwargs["db_path"] = db_path
            if "memory_store" in sig.parameters and "memory_store" not in call_kwargs:
                call_kwargs["memory_store"] = memory_store

            try:
                # Call handler with kwargs or positional args if signature doesn't take kwargs
                if inspect.iscoroutinefunction(handler):
                    try:
                        res = await handler(**call_kwargs)
                    except TypeError:
                        res = await handler(call_kwargs)
                else:
                    try:
                        res = handler(**call_kwargs)
                    except TypeError:
                        res = handler(call_kwargs)

                if inspect.isawaitable(res):
                    res = await res
            except Exception as exc:
                res = ToolResult(
                    success=False,
                    error=f"Tool execution failed: {exc}",
                )

            context.record_tool_invocation(name, call_kwargs, res)
            return res

        # Build mock stream provider
        turns_source = mock_responses or task.mock_responses or task.mock_turns or []

        class MockStreamManager:
            def __init__(self, turns: List[Any], custom_fn: Optional[Callable] = None):
                self.turns = list(turns)
                self.custom_fn = custom_fn
                self.req_idx = 0

            async def stream_chat(self, payload: dict):
                nonlocal step_counter, estimated_token_count
                step_counter += 1

                # Token accounting via NativeOrchestrator.count_tokens
                for m in payload.get("messages", []):
                    c = m.get("content", "")
                    if isinstance(c, str):
                        estimated_token_count += NativeOrchestrator.count_tokens(c)

                if self.custom_fn:
                    res = self.custom_fn(payload)
                    if inspect.isasyncgen(res):
                        async for chunk in res:
                            yield chunk
                        return
                    elif inspect.isgenerator(res):
                        for chunk in res:
                            yield chunk
                        return
                    elif inspect.isawaitable(res):
                        res = await res

                if self.req_idx < len(self.turns):
                    turn = self.turns[self.req_idx]
                    self.req_idx += 1

                    if isinstance(turn, MockTurn):
                        if turn.exception is not None:
                            raise turn.exception
                        for chunk in turn.chunks:
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            c = delta.get("content", "")
                            if c:
                                estimated_token_count += NativeOrchestrator.count_tokens(c)
                            yield chunk
                    elif isinstance(turn, dict):
                        # Could be assistant message format or raw chunk
                        if "choices" in turn:
                            yield turn
                        elif turn.get("role") == "assistant":
                            # Convert assistant message format to SSE delta chunks
                            if "tool_calls" in turn:
                                yield {
                                    "choices": [
                                        {
                                            "delta": {
                                                "tool_calls": [
                                                    {
                                                        "index": 0,
                                                        "id": tc.get("id", "mock_call_1"),
                                                        "type": "function",
                                                        "function": {
                                                            "name": tc.get("function", {}).get("name") or tc.get("name"),
                                                            "arguments": (
                                                                tc.get("function", {}).get("arguments")
                                                                if isinstance(tc.get("function", {}).get("arguments"), str)
                                                                else json.dumps(tc.get("function", {}).get("arguments") or tc.get("arguments", {}))
                                                            ),
                                                        },
                                                    }
                                                    for tc in turn.get("tool_calls", [])
                                                ]
                                            }
                                        }
                                    ]
                                }
                            elif "content" in turn:
                                content = turn.get("content", "")
                                estimated_token_count += NativeOrchestrator.count_tokens(content)
                                yield {"choices": [{"delta": {"content": content}}]}
                        else:
                            yield turn
                    elif isinstance(turn, str):
                        estimated_token_count += NativeOrchestrator.count_tokens(turn)
                        yield {"choices": [{"delta": {"content": turn}}]}
                else:
                    yield {"choices": [{"delta": {"content": "[Mock turns exhausted]"}}]}

        stream_mgr = MockStreamManager(turns_source, custom_fn=mock_stream_fn or task.mock_stream_fn)

        try:
            # Setup hook
            if task.setup_fn:
                s_res = task.setup_fn(temp_dir, memory_store)
                if inspect.isawaitable(s_res):
                    await s_res
            elif task.setup_hook:
                s_res = task.setup_hook(context)
                if inspect.isawaitable(s_res):
                    await s_res

            orchestrator = NativeOrchestrator(
                max_depth=task.max_steps,
                stream_provider=stream_mgr.stream_chat,
                tool_schemas=task.tool_schemas,
                tool_executor=scoped_tool_executor,
                db_path=str(db_path),
            )

            payload = {
                "messages": [{"role": "user", "content": task.user_prompt or task.description}],
                "tools": list(task.tool_schemas or []),
            }

            async def _execute_stream():
                async for chunk in orchestrator.generate_stream(payload):
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    c = delta.get("content", "")
                    if c:
                        context.final_response += c

            await asyncio.wait_for(_execute_stream(), timeout=task.timeout_seconds)

            # Step limit enforcement
            if f"Reached maximum autonomous ReAct steps ({task.max_steps})" in context.final_response:
                context.step_limit_hit = True
                status = EvalStatus.STEP_LIMIT_EXCEEDED
                failure_category = "STEP_LIMIT_EXCEEDED"
                status_message = f"Reached maximum autonomous ReAct steps ({task.max_steps})."
            else:
                # Independent state validator
                val_fn = task.validator_fn or task.validator
                if val_fn:
                    v_res = val_fn(context)
                    if inspect.isawaitable(v_res):
                        v_res = await v_res

                    if isinstance(v_res, tuple):
                        ok, reason = v_res
                    elif hasattr(v_res, "success"):
                        ok, reason = v_res.success, v_res.message
                    else:
                        ok, reason = bool(v_res), str(v_res)

                    if ok:
                        status = EvalStatus.PASS
                        status_message = reason
                    else:
                        # Check for FALSE_SUCCESS claim
                        r_lower = context.final_response.lower()
                        success_claim_words = [
                            "successfully", "created", "completed", "finished",
                            "done", "have written", "has been saved", "all results",
                        ]
                        claims_completion = any(w in r_lower for w in success_claim_words)
                        if claims_completion or not context.tool_calls:
                            status = EvalStatus.FALSE_SUCCESS
                            failure_category = "FALSE_SUCCESS"
                            status_message = f"Model claimed success in text without observable state change ({reason})"
                        else:
                            status = EvalStatus.FAIL
                            failure_category = "VALIDATION_FAILED"
                            status_message = reason
                else:
                    status = EvalStatus.UNVERIFIED
                    status_message = "No validator configured."

        except asyncio.TimeoutError:
            status = EvalStatus.TIMEOUT
            failure_category = "TIMEOUT"
            status_message = f"Task execution timed out after {task.timeout_seconds}s"
        except Exception as exc:
            context.execution_error = exc
            status = EvalStatus.TOOL_ERROR
            failure_category = "TOOL_ERROR"
            status_message = str(exc)

        finally:
            context.duration_seconds = time.perf_counter() - start_time
            context.step_count = step_counter

            if task.cleanup_fn:
                try:
                    c_res = task.cleanup_fn(temp_dir)
                    if inspect.isawaitable(c_res):
                        await c_res
                except Exception:
                    pass
            elif task.cleanup_hook:
                try:
                    c_res = task.cleanup_hook(context)
                    if inspect.isawaitable(c_res):
                        await c_res
                except Exception:
                    pass

            # Always clean up temporary workspace
            shutil.rmtree(temp_dir, ignore_errors=True)

        return TaskResult(
            task_id=task.task_id,
            status=status,
            message=status_message,
            step_count=context.step_count,
            tool_calls=tool_names_called,
            duration_seconds=context.duration_seconds,
            measured_tokens=None,
            estimated_tokens=estimated_token_count,
            failure_category=failure_category,
            artifacts={"final_response": context.final_response},
        )

    # Backward compatibility with EvaluationHarness.execute_task
    async def execute_task(self, task: Any) -> EvaluationResult:
        res = await self.run_task(task)
        # Map EvalStatus to ResultStatus
        status_map = {
            EvalStatus.PASS: ResultStatus.PASS,
            EvalStatus.FAIL: ResultStatus.FAIL,
            EvalStatus.FALSE_SUCCESS: ResultStatus.FAIL,
            EvalStatus.STEP_LIMIT_EXCEEDED: ResultStatus.STEP_LIMIT_EXCEEDED,
            EvalStatus.TIMEOUT: ResultStatus.TIMEOUT,
            EvalStatus.TOOL_ERROR: ResultStatus.ERROR,
            EvalStatus.UNVERIFIED: ResultStatus.UNVERIFIED,
        }
        mapped_status = status_map.get(res.status, ResultStatus.FAIL)
        failure_cat = res.failure_category
        if failure_cat == "FALSE_SUCCESS":
            failure_cat = "VALIDATION_FAILED"

        return EvaluationResult(
            task_id=res.task_id,
            status=mapped_status,
            benchmark_level=getattr(task, "benchmark_level", 1),
            step_count=res.step_count,
            model_requests_count=res.step_count,
            tool_call_count=len(res.tool_calls),
            tool_sequence=list(res.tool_calls),
            duration_seconds=res.duration_seconds,
            failure_category=failure_cat,
            validator_message=res.message,
            error_message=res.message if res.status == EvalStatus.TOOL_ERROR else None,
            measured_tokens=None,
            estimated_tokens={"total_tokens": res.estimated_tokens},
            cleanup_success=True,
        )

    async def run_suite(self, tasks: List[Any], suite_name: str = "Benchmark Suite") -> Any:
        from axiom.eval.report import BenchmarkReport
        results = [await self.execute_task(t) for t in tasks]
        return BenchmarkReport(suite_name=suite_name, results=results)


# Compatibility alias
EvaluationHarness = EvalHarness
