"""Comprehensive unit and integration test suite for AXIOM Evaluation Harness (Phase 1)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from axiom.eval.harness import EvalHarness
from axiom.eval.metrics import EvalStatus, export_json_report, format_summary_table
from axiom.eval.task import EvalContext
from axiom.eval.tasks.deterministic_p1 import (
    build_task_false_success_rejection,
    build_task_memory_persistence_roundtrip,
    build_task_recovery_envelope,
    build_task_step_limit_enforcement,
    build_task_timeout_containment,
    build_task_tool_dispatch,
    get_deterministic_p1_tasks,
)


class TestEvalHarnessP1(unittest.IsolatedAsyncioTestCase):
    """Test suite covering deterministic orchestration, independent validators, and metrics."""

    async def asyncSetUp(self) -> None:
        self.harness = EvalHarness()

    async def test_harness_successful_task_passes(self) -> None:
        """Verify valid task lifecycle dispatches tool and achieves PASS status."""
        task = build_task_tool_dispatch()
        result = await self.harness.run_task(task)

        self.assertEqual(result.status, EvalStatus.PASS)
        self.assertTrue(result.is_success)
        self.assertIn("verified file contents", result.message)
        self.assertIn("mock_read_file", result.tool_calls)
        self.assertGreater(result.step_count, 0)
        self.assertGreater(result.estimated_tokens, 0)
        self.assertIsNone(result.measured_tokens)

    async def test_harness_catches_false_success(self) -> None:
        """Verify model prose claiming completion without real side-effects is rejected as FALSE_SUCCESS."""
        task = build_task_false_success_rejection()
        result = await self.harness.run_task(task)

        self.assertEqual(result.status, EvalStatus.FALSE_SUCCESS)
        self.assertFalse(result.is_success)
        self.assertEqual(result.failure_category, "FALSE_SUCCESS")
        self.assertIn("Model claimed success in text without observable state change", result.message)

    async def test_harness_enforces_step_limit(self) -> None:
        """Verify non-terminating loops are strictly halted at max_steps with STEP_LIMIT_EXCEEDED."""
        task = build_task_step_limit_enforcement()
        result = await self.harness.run_task(task)

        self.assertEqual(result.status, EvalStatus.STEP_LIMIT_EXCEEDED)
        self.assertEqual(result.failure_category, "STEP_LIMIT_EXCEEDED")
        self.assertEqual(result.step_count, 3)

    async def test_harness_remedy_recovery_flow(self) -> None:
        """Verify orchestrator recovers from ToolResult structured error and executes remedy tool."""
        task = build_task_recovery_envelope()
        result = await self.harness.run_task(task)

        self.assertEqual(result.status, EvalStatus.PASS)
        self.assertIn("Recovery envelope successfully processed", result.message)
        self.assertEqual(result.tool_calls, ["read_locked_file", "unlock_file", "read_locked_file"])

    async def test_harness_timeout_cancellation(self) -> None:
        """Verify long-running or blocking tasks abort cleanly with TIMEOUT."""
        task = build_task_timeout_containment()
        result = await self.harness.run_task(task)

        self.assertEqual(result.status, EvalStatus.TIMEOUT)
        self.assertEqual(result.failure_category, "TIMEOUT")
        self.assertIn("timed out", result.message)

    async def test_harness_workspace_and_db_isolation(self) -> None:
        """Verify evaluation executes strictly inside temporary workspace without host pollution."""
        task = build_task_memory_persistence_roundtrip()
        result = await self.harness.run_task(task)

        self.assertEqual(result.status, EvalStatus.PASS)
        self.assertIn("query_memory", result.tool_calls)

        # Confirm no test_eval.db remains in cwd or /tmp root
        self.assertFalse(Path("test_eval.db").exists())
        self.assertFalse(Path("/tmp/test_eval.db").exists())

    async def test_metrics_and_token_distinction(self) -> None:
        """Verify telemetry distinguishes estimated vs measured tokens and serializes valid JSON report."""
        t1 = build_task_tool_dispatch()
        t2 = build_task_false_success_rejection()

        res1 = await self.harness.run_task(t1)
        res2 = await self.harness.run_task(t2)

        results = [res1, res2]
        table_str = format_summary_table(results)
        self.assertIn("AXIOM DETERMINISTIC EVALUATION BENCHMARK REPORT", table_str)
        self.assertIn("task_tool_dispatch", table_str)
        self.assertIn("task_false_success_rejection", table_str)

        with tempfile.TemporaryDirectory() as tmp_dir:
            json_file = Path(tmp_dir) / "eval_report.json"
            export_json_report(results, json_file)
            self.assertTrue(json_file.exists())

            data = json.loads(json_file.read_text(encoding="utf-8"))
            self.assertEqual(data["summary"]["total"], 2)
            self.assertEqual(data["summary"]["passed"], 1)
            self.assertEqual(data["summary"]["false_success"], 1)

            # Strict verification of measured_tokens vs estimated_tokens distinction
            for r in data["results"]:
                self.assertIsNone(r["measured_tokens"])
                self.assertIsInstance(r["estimated_tokens"], int)
                self.assertGreater(r["estimated_tokens"], 0)

    async def test_full_deterministic_p1_suite(self) -> None:
        """Verify the full 6-task deterministic suite executes cleanly with expected classifications."""
        tasks = get_deterministic_p1_tasks()
        self.assertEqual(len(tasks), 6)

        results = {}
        for t in tasks:
            res = await self.harness.run_task(t)
            results[t.task_id] = res

        self.assertEqual(results["task_tool_dispatch"].status, EvalStatus.PASS)
        self.assertEqual(results["task_recovery_envelope"].status, EvalStatus.PASS)
        self.assertEqual(results["task_step_limit_enforcement"].status, EvalStatus.STEP_LIMIT_EXCEEDED)
        self.assertEqual(results["task_false_success_rejection"].status, EvalStatus.FALSE_SUCCESS)
        self.assertEqual(results["task_memory_persistence_roundtrip"].status, EvalStatus.PASS)
        self.assertEqual(results["task_timeout_containment"].status, EvalStatus.TIMEOUT)

    def test_workspace_path_traversal_prevention(self) -> None:
        """Verify that attempting to escape workspace_dir via relative path traversal raises ValueError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            workspace.mkdir()
            db_path = Path(tmp_dir) / "test.db"
            task = build_task_tool_dispatch()
            ctx = EvalContext(task=task, workspace_dir=workspace, db_path=db_path)

            # Valid paths within workspace should resolve successfully
            valid_path = ctx.resolve_path("subdir/file.txt")
            self.assertEqual(valid_path, (workspace / "subdir/file.txt").resolve())

            # Traversal attempts escaping workspace must raise ValueError
            with self.assertRaises(ValueError) as cm:
                ctx.resolve_path("../../etc/shadow")
            self.assertIn("Path traversal detected", str(cm.exception))

            with self.assertRaises(ValueError) as cm2:
                ctx.resolve_path("../other_folder")
            self.assertIn("Path traversal detected", str(cm2.exception))


if __name__ == "__main__":
    unittest.main()
