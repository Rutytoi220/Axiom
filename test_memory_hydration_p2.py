"""Unit and integration test suite for Phase 2: Relevance-Based Retrieval & Token-Budgeted Prompt Hydration.

Verifies:
1. Query matching & category formatting ([Contextual Memory]: <recalled_memory> ...).
2. Hard 350-token ceiling under high-volume candidate matching.
3. Zero-token injection for empty or irrelevant queries.
4. Selective access_count increments for actually injected memories.
5. NativeOrchestrator payload integration on depth == 0, with bypass on depth > 0, retry, and recovery turns.
"""

import os
import re
import tempfile
import unittest
from pathlib import Path

from axiom.db.memory import MemoryStore, get_connection
from axiom.memory.hydration import format_contextual_memory, hydrate_context_memory
from axiom.agents.native_orchestrator import NativeOrchestrator


class TestMemoryHydrationP2(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_hydration_p2.db")
        self.store = MemoryStore(db_path=self.db_path)
        os.environ["AXIOM_MEMORY_DB"] = self.db_path

    def tearDown(self):
        self.temp_dir.cleanup()
        if "AXIOM_MEMORY_DB" in os.environ:
            del os.environ["AXIOM_MEMORY_DB"]

    def test_query_matching_and_category_formatting(self):
        """Verify matched memories are formatted cleanly into [Contextual Memory] block."""
        id1 = self.store.store(
            content="zsh with starship prompt",
            category="preference",
            key="user.shell",
            confidence=1.0,
        )
        id2 = self.store.store(
            content="192.168.1.100 proxmox node",
            category="homelab",
            key="server.ip",
            confidence=0.9,
        )
        id3 = self.store.store(
            content="Always use git rebase on main branch",
            category="workflow",
            key=None,
            confidence=0.95,
        )

        # 1. Query for shell
        block_shell = hydrate_context_memory("What user.shell is configured?", store=self.store)
        self.assertIn("[Contextual Memory]:", block_shell)
        self.assertIn("<recalled_memory>", block_shell)
        self.assertIn("</recalled_memory>", block_shell)
        self.assertIn("- (preference) user.shell: zsh with starship prompt", block_shell)
        self.assertNotIn("proxmox", block_shell)

        # 2. Query for homelab server
        block_server = hydrate_context_memory("server.ip proxmox node", store=self.store)
        self.assertIn("- (homelab) server.ip: 192.168.1.100 proxmox node", block_server)

        # 3. Query for keyless memory
        block_workflow = hydrate_context_memory("rebase main branch", store=self.store)
        self.assertIn("- (workflow) Always use git rebase on main branch", block_workflow)

    def test_hard_token_ceiling_with_high_volume_matching(self):
        """Enforce strict ceiling of <= 350 tokens under heavy memory volume."""
        # Insert 30 matching memories each containing ~30 words (approx 40 tokens)
        for i in range(30):
            self.store.store(
                content=f"Kubernetes cluster node {i} configuration parameters with distributed raft consensus logging and telemetry enabled on homelab subnet {i}",
                category="homelab",
                key=f"cluster.node_{i}",
                confidence=1.0,
            )

        relevant = self.store.get_relevant_memories("cluster homelab", max_tokens=350)
        self.assertGreater(len(relevant), 0)
        # 30 items * ~40 tokens = 1200 tokens. Strict 350 tokens should cap to ~6-8 items
        self.assertLess(len(relevant), 15)

        formatted = format_contextual_memory(relevant)
        token_count = NativeOrchestrator.count_tokens(formatted)
        self.assertLessEqual(token_count, 350, f"Token count {token_count} exceeds 350 ceiling!")
        self.assertGreater(token_count, 50)
        self.assertIn("[Contextual Memory]:", formatted)
        self.assertIn("<recalled_memory>", formatted)

    def test_zero_token_injection_for_empty_or_irrelevant_query(self):
        """When query is empty or completely irrelevant, zero tokens are injected."""
        self.store.store(
            content="Postgres database port is 5432",
            category="environment",
            key="db.port",
        )

        # Empty query
        empty_block = hydrate_context_memory("", store=self.store)
        self.assertEqual(empty_block, "")

        # Whitespace query
        ws_block = hydrate_context_memory("    ", store=self.store)
        self.assertEqual(ws_block, "")

        # Completely non-matching query
        irrelevant_block = hydrate_context_memory("quantum_superposition_xyz_9999", store=self.store)
        self.assertEqual(irrelevant_block, "")

    def test_access_count_increments_on_injection(self):
        """Only memories actually selected and injected have their access_count incremented."""
        id1 = self.store.store(content="Primary editor is Neovim", category="preference", key="user.editor")
        id2 = self.store.store(content="Secondary machine is Raspberry Pi", category="homelab", key="lab.rpi")

        # Initially 0
        self.assertEqual(self.store.get(id1)["access_count"], 1)  # get() increments to 1
        self.assertEqual(self.store.get(id2)["access_count"], 1)

        # Query matching only id1
        _ = self.store.get_relevant_memories("Neovim editor", max_tokens=350, update_access=True)

        mem1 = self.store.get(id1)
        mem2 = self.store.get(id2)
        # id1 was injected and retrieved: access_count increased
        self.assertGreaterEqual(mem1["access_count"], 3)
        # id2 was NOT injected, its access_count only incremented from our get() call
        self.assertEqual(mem2["access_count"], 2)

    async def test_native_orchestrator_depth0_hydration_integration(self):
        """Verify NativeOrchestrator integrates hydration on depth 0 and bypasses on depth > 0, retry, or recovery."""
        self.store.store(
            content="zsh with starship prompt",
            category="preference",
            key="user.shell",
            confidence=1.0,
        )

        orch = NativeOrchestrator()

        # Case 1: Standard depth == 0 turn -> Should hydrate
        payload_standard = {
            "messages": [{"role": "user", "content": "What is my favorite user.shell?"}],
            "tools": [],
        }
        async for _ in orch.generate_stream(payload_standard, depth=0, is_retry=False):
            break

        sys_msg = payload_standard["messages"][0]["content"]
        self.assertIn("[Contextual Memory]:", sys_msg)
        self.assertIn("- (preference) user.shell: zsh with starship prompt", sys_msg)

        # Case 2: depth == 1 -> Should NOT hydrate
        payload_depth1 = {
            "messages": [
                {"role": "system", "content": "Base instructions."},
                {"role": "user", "content": "What is my favorite user.shell?"},
            ],
            "tools": [],
        }
        async for _ in orch.generate_stream(payload_depth1, depth=1, is_retry=False):
            break
        sys_msg_d1 = payload_depth1["messages"][0]["content"]
        self.assertNotIn("[Contextual Memory]:", sys_msg_d1)

        # Case 3: is_retry == True -> Should NOT hydrate
        payload_retry = {
            "messages": [{"role": "user", "content": "What is my favorite user.shell?"}],
            "tools": [],
        }
        async for _ in orch.generate_stream(payload_retry, depth=0, is_retry=True):
            break
        sys_msg_retry = payload_retry["messages"][0]["content"]
        self.assertNotIn("[Contextual Memory]:", sys_msg_retry)

        # Case 4: Preceding turn is tool error recovery turn -> Should NOT hydrate
        payload_recovery = {
            "messages": [
                {"role": "user", "content": "Click the submit button"},
                {"role": "assistant", "content": "Calling click_element", "tool_calls": [{"id": "1", "type": "function", "function": {"name": "interact_with_browser"}}]},
                {"role": "tool", "content": "[Tool Error]: Element not found. Recovery Hint: switch tab"}
            ],
            "tools": [],
        }
        async for _ in orch.generate_stream(payload_recovery, depth=0, is_retry=False):
            break
        # First message after injection is system message
        sys_msg_recovery = payload_recovery["messages"][0]["content"]
        self.assertNotIn("[Contextual Memory]:", sys_msg_recovery)


if __name__ == "__main__":
    unittest.main()
