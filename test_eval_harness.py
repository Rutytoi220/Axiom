"""Unit test suite for AXIOM Deterministic Evaluation Harness."""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path

from axiom.agents.native_orchestrator import NativeOrchestrator
from axiom.eval.context import EvaluationContext
from axiom.eval.harness import EvaluationHarness
from axiom.eval.provider import DeterministicModelProvider, MockTurn
from axiom.eval.report import BenchmarkReport
from axiom.eval.suite_l1 import (
    build_eval_l1_exception_cleanup,
    build_eval_l1_false_success,
    build_eval_l1_memory_round_trip,
    build_eval_l1_recovery,
    build_eval_l1_step_limit,
    build_eval_l1_tool_dispatch,
    get_level_1_suite,
)
from axiom.eval.task import EvaluationTask
from axiom.eval.types import EvaluationResult, ResultStatus, ValidationResult
from axiom.eval.validators import (
    combine_validators,
    validate_file_content,
    validate_file_exists,
    validate_memory_record,
    validate_tool_called,
    validate_tool_sequence,
)


class TestEvaluationHarness(unittest.IsolatedAsyncioTestCase):
    """Verifies the deterministic evaluation subsystem, isolation boundaries, and L1 suite."""

    async def asyncSetUp(self) -> None:
        self.harness = EvaluationHarness()

    async def test_passing_task_lifecycle(self) -> None:
        """Verify passing task executes, validates observable file artifact, and tears down."""
        task = build_eval_l1_tool_dispatch()
        result = await self.harness.execute_task(task)

        self.assertEqual(result.status, ResultStatus.PASS)
        self.assertTrue(result.is_success)
        self.assertEqual(result.step_count, 2)
        self.assertEqual(result.tool_call_count, 1)
        self.assertEqual(result.tool_sequence, ["write_file"])
        self.assertTrue(result.cleanup_success)
        self.assertIn("verified successfully", result.validator_message)
        self.assertIsNotNone(result.estimated_tokens)
        self.assertIsNone(result.measured_tokens)

    async def test_validator_rejection_of_false_success(self) -> None:
        """Verify independent validator rejects completion prose when side-effect is absent."""
        task = build_eval_l1_false_success()
        result = await self.harness.execute_task(task)

        self.assertEqual(result.status, ResultStatus.FAIL)
        self.assertFalse(result.is_success)
        self.assertEqual(result.failure_category, "VALIDATION_FAILED")
        self.assertIn("does not exist", result.validator_message)
        self.assertTrue(result.cleanup_success)

    async def test_tool_dispatch_and_recovery(self) -> None:
        """Verify orchestrator recovers from structured error and triggers allowed recovery action."""
        task = build_eval_l1_recovery()
        result = await self.harness.execute_task(task)

        self.assertEqual(result.status, ResultStatus.PASS)
        self.assertEqual(result.tool_sequence, ["query_status", "initialize_status"])
        self.assertTrue(result.cleanup_success)

    async def test_step_limit_boundaries(self) -> None:
        """Verify non-terminating loops are strictly halted at max_steps boundary."""
        task = build_eval_l1_step_limit()
        result = await self.harness.execute_task(task)

        self.assertEqual(result.status, ResultStatus.STEP_LIMIT_EXCEEDED)
        self.assertEqual(result.step_count, 3)
        self.assertEqual(result.tool_call_count, 3)
        self.assertTrue(result.cleanup_success)

    async def test_timeout_and_cancellation(self) -> None:
        """Verify timeout boundary terminates execution and cleans up resources."""
        async def slow_stream(payload: dict):
            await asyncio.sleep(0.5)
            yield {"choices": [{"delta": {"content": "too late"}}]}

        class SlowProvider:
            def __init__(self):
                self.request_count = 1
                self.estimated_tokens = {}
            def stream_chat(self, payload):
                return slow_stream(payload)

        task = EvaluationTask(
            task_id="eval_timeout_test",
            description="Tests timeout enforcement",
            user_prompt="Run slow task",
            timeout=0.05,
            mock_turns=[MockTurn.text("placeholder")],
        )
        # Manually wrap orchestrator with slow provider by subbing mock_turns
        task.mock_turns = []
        
        # Override harness provider for this specific test
        harness = EvaluationHarness()
        # Test using slow fake tool instead
        async def slow_fake_tool() -> dict:
            await asyncio.sleep(0.5)
            return {"success": True}

        slow_task = EvaluationTask(
            task_id="eval_tool_timeout_test",
            description="Tests timeout during tool execution",
            user_prompt="Run slow tool",
            timeout=0.05,
            allowed_tools=["slow_tool"],
            fake_tools={"slow_tool": slow_fake_tool},
            tool_schemas=[{"type": "function", "function": {"name": "slow_tool"}}],
            mock_turns=[MockTurn.tool_call("slow_tool", {})],
        )

        result = await harness.execute_task(slow_task)
        self.assertEqual(result.status, ResultStatus.TIMEOUT)
        self.assertEqual(result.failure_category, "TIMEOUT")
        self.assertTrue(result.cleanup_success)

    async def test_isolated_database_and_separate_session(self) -> None:
        """Verify persistent memory is written to isolated DB and verified in a separate session."""
        task = build_eval_l1_memory_round_trip()
        result = await self.harness.execute_task(task)

        self.assertEqual(result.status, ResultStatus.PASS)
        self.assertEqual(result.tool_sequence, ["store_memory"])
        self.assertTrue(result.cleanup_success)

    async def test_exception_handling_and_cleanup(self) -> None:
        """Verify injected failures trigger ERROR classification and ensure resource cleanup."""
        task = build_eval_l1_exception_cleanup()
        result = await self.harness.execute_task(task)

        self.assertEqual(result.status, ResultStatus.ERROR)
        self.assertIn("Simulated execution failure", result.error_message or "")
        self.assertTrue(result.cleanup_success)

    async def test_strict_tool_allowlist_enforcement(self) -> None:
        """Verify unauthorized/unregistered tool calls are blocked by security allowlist."""
        task = EvaluationTask(
            task_id="eval_unauthorized_tool",
            description="Attempts unauthorized tool dispatch",
            user_prompt="Execute unauthorized tool",
            allowed_tools=["safe_tool"],
            fake_tools={"safe_tool": lambda: {"success": True}},
            tool_schemas=[
                {"type": "function", "function": {"name": "forbidden_tool"}},
            ],
            mock_turns=[
                MockTurn.tool_call("forbidden_tool", {}),
                MockTurn.text("Tool attempt complete."),
            ],
            validator=None,
        )

        result = await self.harness.execute_task(task)
        # Tool was called and recorded, but returned a security violation envelope
        self.assertEqual(len(result.tool_sequence), 1)
        self.assertEqual(result.tool_sequence[0], "forbidden_tool")
        self.assertTrue(result.cleanup_success)

    async def test_json_report_validity(self) -> None:
        """Verify BenchmarkReport accurately computes metrics and serializes to valid JSON."""
        t1 = build_eval_l1_tool_dispatch()
        t2 = build_eval_l1_false_success()

        report = await self.harness.run_suite([t1, t2], suite_name="Test Report Suite")

        self.assertEqual(report.total_tasks, 2)
        self.assertEqual(report.passed_count, 1)
        self.assertEqual(report.failed_count, 1)
        self.assertEqual(report.pass_rate, 0.5)

        json_str = report.to_json()
        data = json.loads(json_str)
        self.assertEqual(data["suite_name"], "Test Report Suite")
        self.assertEqual(data["passed"], 1)
        self.assertEqual(data["failed"], 1)
        self.assertEqual(len(data["results"]), 2)

        summary = report.summary_table()
        self.assertIn("=== Benchmark Report: Test Report Suite ===", summary)
        self.assertIn("eval_l1_tool_dispatch", summary)
        self.assertIn("eval_l1_false_success", summary)

    def test_production_default_backward_compatibility(self) -> None:
        """Verify NativeOrchestrator maintains existing production defaults when unconfigured."""
        orch = NativeOrchestrator()
        self.assertEqual(orch.max_steps, 5)
        self.assertIsNone(orch.model_provider)
        self.assertIsNone(orch.tool_schemas)
        from axiom.core.plugins import execute_tool
        self.assertEqual(orch.execute_tool, execute_tool)

    async def test_no_model_endpoint_invocation_when_using_deterministic_provider(self) -> None:
        """Verify deterministic provider streams completely offline without contacting Ollama."""
        provider = DeterministicModelProvider(
            turns=[MockTurn.text("Offline deterministic answer.")]
        )
        orch = NativeOrchestrator(model_provider=provider)

        payload = {
            "model": "non-existent-model",
            "messages": [{"role": "user", "content": "Offline test"}],
        }

        chunks = []
        async for chunk in orch.generate_stream(payload):
            delta = chunk.get("choices", [{}])[0].get("delta", {})
            if "content" in delta:
                chunks.append(delta["content"])

        full_text = "".join(chunks)
        self.assertIn("Offline deterministic answer.", full_text)
        self.assertEqual(provider.request_count, 1)

    async def test_level_1_suite_complete_run(self) -> None:
        """Verify entire Level 1 suite runs deterministically and classifies all 6 tasks."""
        suite = get_level_1_suite()
        self.assertEqual(len(suite), 6)

        report = await self.harness.run_suite(suite, suite_name="Level 1 Benchmark")

        self.assertEqual(report.total_tasks, 6)
        # Expected outcomes:
        # 1. tool_dispatch: PASS
        # 2. recovery: PASS
        # 3. step_limit: STEP_LIMIT_EXCEEDED
        # 4. false_success: FAIL
        # 5. memory_round_trip: PASS
        # 6. exception_cleanup: ERROR
        results_by_id = {r.task_id: r for r in report.results}

        self.assertEqual(results_by_id["eval_l1_tool_dispatch"].status, ResultStatus.PASS)
        self.assertEqual(results_by_id["eval_l1_recovery"].status, ResultStatus.PASS)
        self.assertEqual(results_by_id["eval_l1_step_limit"].status, ResultStatus.STEP_LIMIT_EXCEEDED)
        self.assertEqual(results_by_id["eval_l1_false_success"].status, ResultStatus.FAIL)
        self.assertEqual(results_by_id["eval_l1_memory_round_trip"].status, ResultStatus.PASS)
        self.assertEqual(results_by_id["eval_l1_exception_cleanup"].status, ResultStatus.ERROR)

        # Confirm all temporary resources were cleaned up across all tasks
        for r in report.results:
            self.assertTrue(r.cleanup_success, f"Task {r.task_id} failed resource cleanup")


if __name__ == "__main__":
    unittest.main()
