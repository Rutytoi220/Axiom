"""Unit and integration test suite for ToolValidator & Isolated Staging Pipeline.

Verifies:
1. Valid tool code passes all checks (AST, schema, ring validation, isolated staging run).
2. Syntax errors are caught with line numbers and abort prior to staging.
3. Missing required exports (execute, TOOL_SCHEMA, TUI_HINT, REQUIRED_RING, TIER) fail with clear contract errors.
4. Ring conformance: invalid or disallowed ring values fail validation.
5. Runtime exception in execute() during staging fails validation and strictly cleans up /tmp/ scratch files.
6. Malformed TOOL_SCHEMA (missing name, non-object parameters, etc.) fails validation.
7. Sync execute function is rejected with explicit async def requirement.
8. Cleanup invariants: zero lingering axiom_stage_*.py files in /tmp/ across all test cases.
"""

from __future__ import annotations

import glob
import os
import unittest
from typing import Any, Dict

from axiom.tools.validator import ToolValidator, ValidationResult


VALID_TOOL_CODE = '''
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "sample_calc_tool",
        "description": "Calculates sum of two numbers for testing.",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "integer", "description": "First number"},
                "b": {"type": "integer", "description": "Second number"}
            },
            "required": ["a", "b"]
        }
    }
}
REQUIRED_RING = 0
TIER = 1
TUI_HINT = "🧮 Calculating sum..."

async def execute(a: int = 0, b: int = 0, **kwargs) -> str:
    return str(a + b)
'''


class TestToolValidator(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.validator = ToolValidator()

    def test_1_valid_tool_passes_ast_and_schema_and_ring(self):
        """Verify standard compliant tool passes syntax, AST, and contract validation."""
        # 1. AST check
        ast_res = self.validator.validate_syntax_and_ast(VALID_TOOL_CODE)
        self.assertTrue(ast_res.is_valid, f"AST validation failed: {ast_res.error}")
        self.assertEqual(ast_res.tier, 1)
        self.assertEqual(ast_res.ring, 0)

        # 2. Ring conformance check
        ring_ok, ring_err = self.validator.validate_ring_conformance(0)
        self.assertTrue(ring_ok)
        self.assertIsNone(ring_err)

        ring_3_ok, _ = self.validator.validate_ring_conformance(3)
        self.assertTrue(ring_3_ok)

        # 3. Schema check
        schema = {
            "type": "function",
            "function": {
                "name": "test_echo",
                "description": "Echo input text.",
                "parameters": {
                    "type": "object",
                    "properties": {"msg": {"type": "string"}},
                    "required": ["msg"],
                },
            },
        }
        schema_ok, schema_err = self.validator.validate_schema(schema)
        self.assertTrue(schema_ok, f"Schema validation failed: {schema_err}")

    async def test_2_valid_tool_passes_isolated_staging_and_validate_all(self):
        """Verify full validate_all pipeline completes successfully on valid tool."""
        res = await self.validator.validate_all(VALID_TOOL_CODE, test_params={"a": 5, "b": 10})
        self.assertTrue(res.is_valid, f"Validation failed: {res.error}")
        self.assertEqual(res.tool_name, "sample_calc_tool")
        self.assertEqual(res.tier, 1)
        self.assertEqual(res.ring, 0)
        self.assertIsNotNone(res.schema)

    def test_3_syntax_error_caught_with_line_number(self):
        """Verify syntax error is caught with line number and col, aborting before staging."""
        broken_code = "import json\n\ndef broken_function(\n    return 42\n"
        res = self.validator.validate_syntax_and_ast(broken_code)
        self.assertFalse(res.is_valid)
        self.assertIn("Syntax error at line", res.error)

    def test_4_missing_required_exports(self):
        """Verify missing contract exports (execute, TOOL_SCHEMA, etc.) produce clear errors."""
        # Missing TUI_HINT
        code_no_hint = '''
TOOL_SCHEMA = {"type": "function", "function": {"name": "test", "description": "test", "parameters": {"type": "object", "properties": {}}}}
REQUIRED_RING = 1
TIER = 1
async def execute(**kwargs): return "ok"
'''
        res = self.validator.validate_syntax_and_ast(code_no_hint)
        self.assertFalse(res.is_valid)
        self.assertIn("Missing required top-level export(s)", res.error)
        self.assertIn("TUI_HINT", res.error)

        # Missing execute function
        code_no_exec = '''
TOOL_SCHEMA = {"type": "function", "function": {"name": "test", "description": "test", "parameters": {"type": "object", "properties": {}}}}
REQUIRED_RING = 1
TIER = 1
TUI_HINT = "Testing..."
'''
        res_exec = self.validator.validate_syntax_and_ast(code_no_exec)
        self.assertFalse(res_exec.is_valid)
        self.assertIn("Missing required async function: 'execute'", res_exec.error)

        # Sync execute function instead of async def
        code_sync_exec = '''
TOOL_SCHEMA = {"type": "function", "function": {"name": "test", "description": "test", "parameters": {"type": "object", "properties": {}}}}
REQUIRED_RING = 1
TIER = 1
TUI_HINT = "Testing..."
def execute(**kwargs): return "ok"
'''
        res_sync = self.validator.validate_syntax_and_ast(code_sync_exec)
        self.assertFalse(res_sync.is_valid)
        self.assertIn("must be an asynchronous function (async def)", res_sync.error)

    def test_5_ring_conformance_checks(self):
        """Verify ring validation rejects negative, out-of-bounds, or non-integer values."""
        ok_neg, err_neg = self.validator.validate_ring_conformance(-1)
        self.assertFalse(ok_neg)
        self.assertIn("must conform to AXIOM ring hierarchy", err_neg)

        ok_high, err_high = self.validator.validate_ring_conformance(4)
        self.assertFalse(ok_high)
        self.assertIn("must conform to AXIOM ring hierarchy", err_high)

        ok_bool, err_bool = self.validator.validate_ring_conformance(True)
        self.assertFalse(ok_bool)
        self.assertIn("must be an integer", err_bool)

        ok_str, err_str = self.validator.validate_ring_conformance("0")
        self.assertFalse(ok_str)
        self.assertIn("must be an integer", err_str)

    def test_6_malformed_tool_schema(self):
        """Verify malformed schemas (missing name, missing properties, invalid type) fail."""
        # Missing function.name
        bad_name_schema = {
            "type": "function",
            "function": {
                "name": "",
                "description": "test",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        ok, err = self.validator.validate_schema(bad_name_schema)
        self.assertFalse(ok)
        self.assertIn("function.name' must be a non-empty string", err)

        # Missing properties
        bad_props_schema = {
            "type": "function",
            "function": {
                "name": "valid_name",
                "description": "test",
                "parameters": {"type": "object"},
            },
        }
        ok, err = self.validator.validate_schema(bad_props_schema)
        self.assertFalse(ok)
        self.assertIn("properties' dictionary", err)

        # Parameters type is not object
        bad_type_schema = {
            "type": "function",
            "function": {
                "name": "valid_name",
                "description": "test",
                "parameters": {"type": "string", "properties": {}},
            },
        }
        ok, err = self.validator.validate_schema(bad_type_schema)
        self.assertFalse(ok)
        self.assertIn("type' must be 'object'", err)

    async def test_7_runtime_exception_during_staging_fails_and_cleans_up(self):
        """Verify runtime exception during staging fails validation and cleans up scratch files."""
        failing_code = '''
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "crash_tool",
        "description": "Throws error at runtime.",
        "parameters": {"type": "object", "properties": {}}
    }
}
REQUIRED_RING = 0
TIER = 1
TUI_HINT = "Crashing..."

async def execute(**kwargs) -> str:
    raise ValueError("Simulated runtime failure in execute()")
'''
        # Check files before
        before_scratch = set(glob.glob("/tmp/axiom_stage_*.py"))

        res = await self.validator.validate_all(failing_code)
        self.assertFalse(res.is_valid)
        self.assertIn("Simulated runtime failure in execute()", res.error)

        # Check files after: no newly lingering axiom_stage_*.py
        after_scratch = set(glob.glob("/tmp/axiom_stage_*.py"))
        diff = after_scratch - before_scratch
        self.assertEqual(len(diff), 0, f"Lingering scratch files detected in /tmp: {diff}")

    def test_8_tier_validation(self):
        """Verify TIER must be an integer in {1, 2, 3}."""
        code_bad_tier = '''
TOOL_SCHEMA = {"type": "function", "function": {"name": "test", "description": "test", "parameters": {"type": "object", "properties": {}}}}
REQUIRED_RING = 0
TIER = 5
TUI_HINT = "Testing..."
async def execute(**kwargs): return "ok"
'''
        res = self.validator.validate_syntax_and_ast(code_bad_tier)
        self.assertFalse(res.is_valid)
        self.assertIn("Invalid TIER '5'", res.error)


if __name__ == "__main__":
    unittest.main()
