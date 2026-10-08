"""Unit and integration test suite for Phase 1: Structured SQLite FTS5 Persistent Memory Store & Concurrency.

Covers:
1. Full CRUD lifecycle (store, get, update, soft-delete, hard-delete, purge_inactive).
2. Key-based automatic superseding and versioning (is_active and superseded_by pointers).
3. Synchronized FTS5 full-text search table across key, content, and category with BM25 ranking.
4. WAL concurrency: 5 concurrent threads reading and writing without database locked errors.
5. Backwards compatibility with chat session history and message logging.
"""

import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from axiom.db.memory import (
    MemoryStore,
    VALID_CATEGORIES,
    init_db,
    get_connection,
    create_session,
    add_message,
    get_session_messages,
    search_historical_context,
)


class TestMemoryStoreP1(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_memory_p1.db")
        self.store = MemoryStore(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_crud_lifecycle(self):
        """Test full CRUD lifecycle including access count and soft/hard delete."""
        # 1. Store
        mem_id = self.store.store(
            content="The user prefers dark mode and high contrast themes.",
            category="preference",
            key="ui.theme",
            confidence=0.95,
        )
        self.assertIsInstance(mem_id, int)
        self.assertGreater(mem_id, 0)

        # 2. Get
        mem = self.store.get(mem_id)
        self.assertIsNotNone(mem)
        self.assertEqual(mem["id"], mem_id)
        self.assertEqual(mem["category"], "preference")
        self.assertEqual(mem["key"], "ui.theme")
        self.assertEqual(mem["content"], "The user prefers dark mode and high contrast themes.")
        self.assertEqual(mem["confidence"], 0.95)
        self.assertEqual(mem["is_active"], 1)
        self.assertIsNone(mem["superseded_by"])
        self.assertEqual(mem["access_count"], 1)

        # Second read increments access count
        mem_again = self.store.get(mem_id)
        self.assertEqual(mem_again["access_count"], 2)

        # 3. Update
        updated = self.store.update(
            mem_id,
            content="The user prefers Tokyo Night dark mode theme.",
            confidence=1.0,
        )
        self.assertTrue(updated)
        mem_updated = self.store.get(mem_id)
        self.assertEqual(mem_updated["content"], "The user prefers Tokyo Night dark mode theme.")
        self.assertEqual(mem_updated["confidence"], 1.0)
        self.assertGreaterEqual(mem_updated["updated_at"], mem["updated_at"])

        # 4. Soft-delete
        deleted = self.store.delete(mem_id, hard_delete=False)
        self.assertTrue(deleted)

        # Still accessible via get(id), but is_active == 0
        mem_soft = self.store.get(mem_id)
        self.assertIsNotNone(mem_soft)
        self.assertEqual(mem_soft["is_active"], 0)

        # get_by_key returns None since it is no longer active
        self.assertIsNone(self.store.get_by_key("ui.theme"))

        # search excludes soft-deleted by default
        search_active = self.store.search("Tokyo Night")
        self.assertEqual(len(search_active), 0)

        # search includes when include_inactive=True
        search_inactive = self.store.search("Tokyo Night", include_inactive=True)
        self.assertEqual(len(search_inactive), 1)
        self.assertEqual(search_inactive[0]["id"], mem_id)

        # 5. Purge inactive
        purged = self.store.purge_inactive()
        self.assertEqual(purged, 1)
        self.assertIsNone(self.store.get(mem_id))

        # 6. Hard-delete test
        new_id = self.store.store(content="Temporary memory to hard delete", category="capability")
        self.assertTrue(self.store.delete(new_id, hard_delete=True))
        self.assertIsNone(self.store.get(new_id))

    def test_key_automatic_superseding(self):
        """Storing a new active memory with the same key must atomically supersede old version."""
        # Version 1
        id_v1 = self.store.store(
            content="User uses bash as default shell",
            category="environment",
            key="user.shell",
            confidence=0.8,
        )
        mem_v1 = self.store.get(id_v1)
        self.assertEqual(mem_v1["is_active"], 1)
        self.assertIsNone(mem_v1["superseded_by"])

        # Version 2
        id_v2 = self.store.store(
            content="User switched to zsh with starship prompt",
            category="environment",
            key="user.shell",
            confidence=0.99,
        )
        self.assertNotEqual(id_v1, id_v2)

        # Verify V1 is now deactivated and points to V2
        mem_v1_after = self.store.get(id_v1)
        self.assertEqual(mem_v1_after["is_active"], 0)
        self.assertEqual(mem_v1_after["superseded_by"], id_v2)

        # Verify V2 is active and points to None
        mem_v2 = self.store.get(id_v2)
        self.assertEqual(mem_v2["is_active"], 1)
        self.assertIsNone(mem_v2["superseded_by"])

        # get_by_key resolves to active V2
        active_shell = self.store.get_by_key("user.shell")
        self.assertIsNotNone(active_shell)
        self.assertEqual(active_shell["id"], id_v2)
        self.assertEqual(active_shell["content"], "User switched to zsh with starship prompt")

    def test_fts5_search_synchronization(self):
        """Verify FTS5 search across content, key, and category with triggers."""
        self.store.store(
            content="Proxmox VE hypervisor running on 192.168.1.100",
            category="homelab",
            key="homelab.proxmox",
        )
        self.store.store(
            content="TrueNAS Core storage server on 192.168.1.105",
            category="homelab",
            key="homelab.nas",
        )
        self.store.store(
            content="Git workflow requires conventional commits and PR squash merge",
            category="workflow",
            key="workflow.git",
        )

        # 1. Search by content keyword
        res_proxmox = self.store.search("Proxmox")
        self.assertEqual(len(res_proxmox), 1)
        self.assertEqual(res_proxmox[0]["key"], "homelab.proxmox")

        # 2. Search by key
        res_key = self.store.search("homelab.nas")
        self.assertEqual(len(res_key), 1)
        self.assertEqual(res_key[0]["key"], "homelab.nas")

        # 3. Search by category
        res_cat = self.store.search("homelab")
        self.assertGreaterEqual(len(res_cat), 2)
        keys = {r["key"] for r in res_cat}
        self.assertIn("homelab.proxmox", keys)
        self.assertIn("homelab.nas", keys)

        # 4. Filter with category constraint
        res_workflow = self.store.search("commits", category="workflow")
        self.assertEqual(len(res_workflow), 1)
        self.assertEqual(res_workflow[0]["category"], "workflow")

        # 5. Search non-matching category returns empty
        res_empty = self.store.search("commits", category="homelab")
        self.assertEqual(len(res_empty), 0)

    def test_category_validation(self):
        """Store must reject invalid categories not defined in CHECK constraint."""
        for cat in VALID_CATEGORIES:
            mem_id = self.store.store(content=f"Valid test for {cat}", category=cat)
            self.assertGreater(mem_id, 0)

        with self.assertRaises(ValueError):
            self.store.store(content="Invalid category test", category="unsupported_cat")

    def test_wal_concurrency(self):
        """Simulate 5 concurrent threads reading and writing simultaneously without DB lock errors."""
        errors = []
        threads = []
        num_threads = 5
        writes_per_thread = 20

        def worker(thread_idx: int):
            try:
                for i in range(writes_per_thread):
                    # Write operation
                    key = f"thread_{thread_idx}.item_{i % 5}"
                    mem_id = self.store.store(
                        content=f"Thread {thread_idx} written item {i} with payload data",
                        category="capability",
                        key=key,
                        confidence=1.0,
                    )

                    # Read operation
                    mem = self.store.get(mem_id)
                    if not mem or mem["id"] != mem_id:
                        errors.append(f"Thread {thread_idx}: get({mem_id}) failed")

                    # Key read operation
                    by_key = self.store.get_by_key(key)
                    if not by_key or by_key["key"] != key:
                        errors.append(f"Thread {thread_idx}: get_by_key({key}) failed")

                    # FTS search operation
                    search_res = self.store.search(f"item {i}")
                    if not search_res:
                        errors.append(f"Thread {thread_idx}: search('item {i}') returned empty")

            except Exception as e:
                errors.append(f"Thread {thread_idx} exception: {e}")

        for t_idx in range(num_threads):
            t = threading.Thread(target=worker, args=(t_idx,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrency errors encountered: {errors}")

        # Check total records in database
        conn = get_connection(self.db_path)
        total_active = conn.execute("SELECT count(*) FROM memories WHERE is_active = 1").fetchone()[0]
        self.assertGreater(total_active, 0)
        conn.close()

    def test_chat_session_history_backwards_compatibility(self):
        """Verify sessions, messages, and messages_fts work without regression."""
        session_id = "test_backwards_session_1"
        create_session(session_id, title="Test Session", db_path=self.db_path)

        add_message(session_id, "user", "What is the status of the server?", db_path=self.db_path)
        add_message(session_id, "assistant", "All systems operational with 99.9% uptime.", db_path=self.db_path)

        msgs = get_session_messages(session_id, db_path=self.db_path)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[0]["content"], "What is the status of the server?")
        self.assertEqual(msgs[1]["role"], "assistant")
        self.assertEqual(msgs[1]["content"], "All systems operational with 99.9% uptime.")

        fts_search = search_historical_context("operational", session_id, db_path=self.db_path)
        self.assertEqual(len(fts_search), 1)
        self.assertIn("All systems operational", fts_search[0])


if __name__ == "__main__":
    unittest.main()
