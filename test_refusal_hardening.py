"""Verification test suite for hardened persona, refusal interception, and active window injection."""

import asyncio
import contextlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

from axiom.agents.native_orchestrator import NativeOrchestrator, REFUSAL_PHRASES


def test_system_prompt_hardening():
    print("[CHECK 1] Testing System Prompt Hardening & Invariants...")
    orch = NativeOrchestrator()
    prompt = orch._build_system_prompt()

    # Verify operational invariants
    assert "OPERATIONAL INVARIANTS" in prompt, "Missing OPERATIONAL INVARIANTS in system prompt"
    assert "STRICT REFUSAL BAN" in prompt, "Missing STRICT REFUSAL BAN in system prompt"
    assert "ZERO-PREAMBLE TOOL DISPATCH" in prompt, "Missing ZERO-PREAMBLE TOOL DISPATCH in system prompt"

    # Verify forbidden phrases are banned
    for phrase in [
        "cannot see your screen",
        "don't have eyes",
        "lack access to your computer",
        "As an AI language model",
    ]:
        assert phrase in prompt, f"Forbidden phrase rule '{phrase}' not stated in refusal ban"

    # Verify three tier tools are specified
    assert "manage_desktop_window" in prompt
    assert "interact_with_browser" in prompt
    assert "interact_with_ui" in prompt

    # Verify few-shot exemplars
    assert "FEW-SHOT TOOL CALL EXEMPLARS" in prompt, "Missing few-shot exemplars"
    assert "Example 1: Desktop" in prompt or "Window Inspection" in prompt
    assert "Button Clicking" in prompt

    print("✓ Check 1 PASSED: System prompt contains refusal ban and few-shot exemplars.\n")


def test_active_window_injection():
    print("[CHECK 2] Testing Proactive Active Window Context Injection...")
    orch = NativeOrchestrator()

    # 1. Test get_active_window_context with mocked hyprctl
    mock_activewindow = json.dumps({
        "title": "Zen Browser - Work",
        "class": "zen-alpha",
        "workspace": {"id": 3, "name": "3"},
    }).encode("utf-8")

    async def run_context_test():
        with patch("shutil.which", return_value="/usr/bin/hyprctl"), \
             patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (mock_activewindow, b"")
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            header = await orch.get_active_window_context()
            assert header == '[Active Window: title="Zen Browser - Work", class="zen-alpha", workspace=3]'

        # 2. Test injection into payload during generate_stream
        payload = {
            "messages": [{"role": "user", "content": "Click the button on my screen"}]
        }
        @contextlib.asynccontextmanager
        async def mock_empty_stream(method, url, **kwargs):
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            async def empty_aiter():
                return
                yield
            mock_resp.aiter_lines = empty_aiter
            yield mock_resp

        with patch.object(orch, "get_active_window_context", return_value='[Active Window: title="Zen Browser - Work", class="zen-alpha", workspace=3]'), \
             patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.stream = mock_empty_stream
            mock_client.return_value.__aenter__.return_value.post = AsyncMock()

            async for _ in orch.generate_stream(payload):
                pass

            # Verify active window telemetry is injected into user message
            user_msgs = [m for m in payload["messages"] if m.get("role") == "user"]
            assert len(user_msgs) > 0
            assert '[Active Window: title="Zen Browser - Work", class="zen-alpha", workspace=3]' in user_msgs[0]["content"]

    asyncio.run(run_context_test())
    print("✓ Check 2 PASSED: Active window context correctly formatted and injected into payload.\n")


def test_refusal_interceptor_and_retry():
    print("[CHECK 3] Testing Refusal Interceptor & Retry Guard...")
    orch = NativeOrchestrator()

    # 1. Test helper classification
    for query in [
        "Click the button on my screen",
        "What window is active right now?",
        "Inspect the open browser tabs",
        "Can you see my screen?",
    ]:
        assert orch.is_interface_action_query(query) is True, f"Failed to classify interface query: {query}"

    assert orch.is_interface_action_query("Write a poem about trees") is False

    for refusal in REFUSAL_PHRASES:
        assert orch.is_refusal(f"I am sorry, but I {refusal}. How can I assist you?") is True
    assert orch.is_refusal("I will invoke the tool manage_desktop_window now.") is False

    # 2. Test stream interception and retry execution
    attempt = 0

    async def run_interceptor_test():
        nonlocal attempt
        payload = {
            "messages": [{"role": "user", "content": "Click the submit button on my screen"}],
            "options": {"temperature": 0.7},
        }

        with patch("axiom.agents.native_orchestrator.execute_tool", new=AsyncMock(return_value={"status": "clicked"})) as mock_exec, \
             patch.object(orch, "get_active_window_context", return_value=None), \
             patch("httpx.AsyncClient") as mock_client:

            @contextlib.asynccontextmanager
            async def mock_stream_handler(method, url, **kwargs):
                nonlocal attempt
                attempt += 1
                resp = AsyncMock()
                resp.status_code = 200

                if attempt == 1:
                    # Initial response: refusal disclaimer
                    lines = [
                        'data: {"choices": [{"delta": {"content": "I cannot see your screen. "}}]}',
                        'data: {"choices": [{"delta": {"content": "As an AI, I do not have access to your computer."}}]}',
                        'data: [DONE]',
                    ]
                else:
                    # Retry response: valid tool call
                    lines = [
                        'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_retry_1", "type": "function", "function": {"name": "interact_with_ui", "arguments": "{\\"action\\": \\"click\\", \\"target\\": \\"submit button\\"}"}}]}}]}',
                        'data: [DONE]',
                    ]

                async def aiter_lines():
                    for l in lines:
                        yield l

                resp.aiter_lines = aiter_lines
                yield resp

            mock_client.return_value.__aenter__.return_value.stream = mock_stream_handler
            mock_client.return_value.__aenter__.return_value.post = AsyncMock()

            yielded_texts = []
            yielded_tool_calls = []

            async for chunk in orch.generate_stream(payload):
                choices = chunk.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    if "content" in delta and delta["content"]:
                        yielded_texts.append(delta["content"])
                    if "tool_calls" in delta:
                        yielded_tool_calls.extend(delta["tool_calls"])

            combined_output = "".join(yielded_texts)

            # Assert refusal disclaimer was NEVER yielded to caller
            assert "cannot see your screen" not in combined_output, "Refusal disclaimer leaked to caller!"
            assert "As an AI" not in combined_output, "Refusal disclaimer leaked to caller!"

            # Assert retry happened
            assert attempt >= 2, f"Expected at least 2 attempts (initial + retry), got {attempt}"

            # Assert internal corrective override was appended
            override_msgs = [
                m for m in payload["messages"]
                if m.get("role") == "user" and "[SYSTEM OVERRIDE]:" in m.get("content", "")
            ]
            assert len(override_msgs) == 1, "SYSTEM OVERRIDE message was not appended to payload"

            # Assert temperature was clamped to 0.1
            assert payload.get("options", {}).get("temperature") == 0.1
            assert payload.get("temperature") == 0.1

            # Assert tool call was emitted
            assert len(yielded_tool_calls) > 0, "No tool call was emitted after retry"
            assert yielded_tool_calls[0]["function"]["name"] == "interact_with_ui"

    asyncio.run(run_interceptor_test())
    print("✓ Check 3 PASSED: Refusal intercepted, discarded, and tool successfully emitted via retry.\n")


if __name__ == "__main__":
    test_system_prompt_hardening()
    test_active_window_injection()
    test_refusal_interceptor_and_retry()
    print("============================================================")
    print("✅ ALL AGENT PERSONA HARDENING & ANTI-REFUSAL TESTS PASSED!")
    print("============================================================")
