"""Tests for axiom.memory.context_manager — token-aware context management."""

import json
import pytest

from axiom.memory.context_manager import (
    ContextManager,
    estimate_tokens,
    estimate_messages_tokens,
    _truncate_to_tokens,
)


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_single_word(self):
        # "hello" = 1 word × 1.3 ≈ 1 token
        assert estimate_tokens("hello") == 1

    def test_multiple_words(self):
        result = estimate_tokens("hello world test")
        assert result == int(3 * 1.3)

    def test_whitespace_only(self):
        assert estimate_tokens("   ") == 0


class TestEstimateMessagesTokens:
    def test_empty_list(self):
        assert estimate_messages_tokens([]) == 0

    def test_single_string_message(self):
        msgs = [{"role": "user", "content": "hello world"}]
        assert estimate_messages_tokens(msgs) > 0

    def test_dict_content(self):
        msgs = [{"role": "system", "content": {"key": "value"}}]
        assert estimate_messages_tokens(msgs) > 0

    def test_missing_content(self):
        msgs = [{"role": "user"}]
        assert estimate_messages_tokens(msgs) == 0


class TestTruncateToTokens:
    def test_short_text_unchanged(self):
        text = "hello world"
        assert _truncate_to_tokens(text, 100) == text

    def test_long_text_truncated(self):
        text = " ".join(["word"] * 200)
        result = _truncate_to_tokens(text, 50)
        assert result.endswith("...")
        assert estimate_tokens(result) <= 60  # small margin

    def test_single_token_limit(self):
        text = "hello world"
        result = _truncate_to_tokens(text, 1)
        assert len(result.split()) <= 2


class TestContextManagerInit:
    def test_defaults(self):
        cm = ContextManager()
        assert cm.max_tokens == 6144
        assert cm.reserve_tokens == 1024
        assert cm.input_budget == 5120

    def test_custom_values(self):
        cm = ContextManager(max_tokens=4096, reserve_tokens=512)
        assert cm.input_budget == 3584

    def test_summary_threshold(self):
        cm = ContextManager(summary_threshold=5)
        assert cm.should_summarize([{"role": "user", "content": "x"}] * 6) is True
        assert cm.should_summarize([{"role": "user", "content": "x"}] * 4) is False


class TestBuildContextWindow:
    def setup_method(self):
        self.cm = ContextManager(max_tokens=2000, reserve_tokens=300)

    def test_minimal_input(self):
        system = [{"role": "system", "content": "You are AXIOM."}]
        result = self.cm.build_context_window(system, [], "do something")
        assert len(result) >= 2
        assert result[0]["role"] == "system"
        assert result[-1]["role"] == "user"

    def test_includes_recent_history(self):
        system = [{"role": "system", "content": "system prompt"}]
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
            {"role": "user", "content": "how are you"},
            {"role": "assistant", "content": "doing well"},
        ]
        result = self.cm.build_context_window(system, history, "task")
        # Should include system + some history + task
        assert len(result) >= 3
        # Task should be present
        task_msgs = [m for m in result if m.get("content") == "task"]
        assert len(task_msgs) == 1

    def test_includes_observations(self):
        system = [{"role": "system", "content": "sys"}]
        observations = [{"tool": "shell", "success": True, "result": {"output": "done"}}]
        result = self.cm.build_context_window(system, [], "task", observations=observations)
        # Find the observations message
        obs_msgs = [m for m in result if "tool results" in m.get("content", "")]
        assert len(obs_msgs) == 1

    def test_budget_respected(self):
        # Create a large system message that uses most of the budget
        big_system = [{"role": "system", "content": "word " * 500}]
        history = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
        result = self.cm.build_context_window(big_system, history, "task")
        total = estimate_messages_tokens(result)
        assert total <= self.cm.input_budget + 200  # estimation margin

    def test_task_always_included(self):
        system = [{"role": "system", "content": "x " * 400}]
        result = self.cm.build_context_window(system, [], "important task")
        task_msgs = [m for m in result if m.get("content") == "important task"]
        assert len(task_msgs) == 1

    def test_system_always_included(self):
        system = [{"role": "system", "content": "critical instructions"}]
        result = self.cm.build_context_window(system, [], "task")
        sys_msgs = [m for m in result if "critical instructions" in m.get("content", "")]
        assert len(sys_msgs) == 1

    def test_retrieved_memories_included(self):
        system = [{"role": "system", "content": "sys"}]
        memories = [{"key": "k1", "value": "important fact"}]
        result = self.cm.build_context_window(
            system, [], "task", retrieved_memories=memories
        )
        mem_msgs = [m for m in result if "Relevant memories" in m.get("content", "")]
        assert len(mem_msgs) == 1

    def test_observations_limited_to_3(self):
        system = [{"role": "system", "content": "sys"}]
        observations = [
            {"tool": "a", "result": "1"},
            {"tool": "b", "result": "2"},
            {"tool": "c", "result": "3"},
            {"tool": "d", "result": "4"},
        ]
        result = self.cm.build_context_window(system, [], "task", observations=observations)
        obs_msgs = [m for m in result if "tool results" in m.get("content", "")]
        assert len(obs_msgs) == 1
        # Should contain only 3 observations
        content = obs_msgs[0]["content"]
        assert content.count('"tool"') == 3

    def test_empty_history(self):
        system = [{"role": "system", "content": "sys"}]
        result = self.cm.build_context_window(system, [], "task")
        assert len(result) >= 2


class TestSummarization:
    def test_should_summarize_threshold(self):
        cm = ContextManager(summary_threshold=4)
        history = [{"role": "user", "content": str(i)} for i in range(10)]
        assert cm.should_summarize(history) is True

    def test_get_turns_for_summary(self):
        cm = ContextManager()
        history = [{"role": "user", "content": str(i)} for i in range(20)]
        older = cm.get_turns_for_summary(history)
        assert len(older) == 8  # 20 - 12 = 8

    def test_summarize_with_custom_fn(self):
        def my_summary(turns):
            return f"Summary of {len(turns)} turns"

        cm = ContextManager(summarize_fn=my_summary)
        turns = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
        result = cm._summarize_turns(turns)
        assert result is not None
        assert "Summary of 2 turns" in result["content"]

    def test_summarize_fallback_includes_both_roles(self):
        cm = ContextManager()
        turns = [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."},
            {"role": "user", "content": "Tell me more."},
            {"role": "assistant", "content": "It was created by Guido."},
        ]
        result = cm._summarize_turns(turns)
        assert result is not None
        assert "User asked" in result["content"]
        assert "Assistant said" in result["content"]

    def test_summarize_empty_turns(self):
        cm = ContextManager()
        assert cm._summarize_turns([]) is None

    def test_summarize_custom_fn_failure_falls_back(self):
        def bad_summary(turns):
            raise RuntimeError("boom")

        cm = ContextManager(summarize_fn=bad_summary)
        turns = [{"role": "user", "content": "hello"}]
        result = cm._summarize_turns(turns)
        assert result is not None  # falls back to default

    def test_summarize_digest_truncated(self):
        cm = ContextManager(summary_max_tokens=20)
        turns = [{"role": "user", "content": "word " * 100}]
        result = cm._summarize_turns(turns)
        assert result is not None
        assert estimate_tokens(result["content"]) <= 30  # small margin


class TestTruncateSection:
    def test_fit_all(self):
        cm = ContextManager()
        msgs = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        result = cm._truncate_section(msgs, 1000)
        assert result is not None
        assert len(result) == 2

    def test_truncate_last(self):
        cm = ContextManager()
        msgs = [
            {"role": "user", "content": "short"},
            {"role": "assistant", "content": "a " * 200},
        ]
        result = cm._truncate_section(msgs, 50)
        assert result is not None
        assert len(result) >= 1
        # First message should be kept
        assert result[0]["content"] == "short"

    def test_empty_input(self):
        cm = ContextManager()
        assert cm._truncate_section([], 100) is None


class TestIntegration:
    def test_full_flow_with_many_turns(self):
        cm = ContextManager(max_tokens=3000, reserve_tokens=500, summary_threshold=6)
        system = [{"role": "system", "content": "You are a helpful assistant."}]
        history = []
        for i in range(20):
            history.append({"role": "user", "content": f"Question {i} about topic {i % 3}"})
            history.append({"role": "assistant", "content": f"Answer {i} with some detail"})

        result = cm.build_context_window(
            system, history, "Final question",
            observations=[{"tool": "test", "result": "ok"}],
        )
        total = estimate_messages_tokens(result)
        assert total <= cm.input_budget + 200
        # System and task always present
        assert any("helpful assistant" in m.get("content", "") for m in result)
        task_msgs = [m for m in result if m.get("content") == "Final question"]
        assert len(task_msgs) == 1

    def test_summary_persists_across_builds(self):
        cm = ContextManager(max_tokens=3000, reserve_tokens=300, summary_threshold=4)
        system = [{"role": "system", "content": "sys"}]
        # Need >12 messages for _get_older_turns to return anything
        history = []
        for i in range(10):
            history.append({"role": "user", "content": f"Question {i}"})
            history.append({"role": "assistant", "content": f"Answer {i}"})

        # First build — should include summary of older turns
        result1 = cm.build_context_window(system, history, "task1")
        summary_msgs = [m for m in result1 if "Earlier conversation" in m.get("content", "")]
        assert len(summary_msgs) == 1
