"""Memory Pruner Daemon for AXIOM.

Runs a daily sweep to summarize and compress old messages, and run VACUUM on the database.
"""
import time
import threading
import logging
import asyncio
import json
import uuid
from typing import Any, Optional
from axiom.core.async_bridge import run_sync

logger = logging.getLogger(__name__)

class MemoryPrunerDaemon:
    """Runs a daily check to prune, summarize, and vacuum the memory database."""

    def __init__(self, memory_store: Any, llm: Optional[Any] = None, interval_days: float = 1.0, retain_days: float = 30.0):
        self._memory_store = memory_store
        self._llm = llm
        self._interval_seconds = interval_days * 24 * 3600
        self._retain_seconds = retain_days * 24 * 3600
        self._is_running = False
        self._thread = None

    def start(self) -> None:
        if self._is_running:
            return
        self._is_running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="MemoryPrunerDaemon")
        self._thread.start()
        logger.info(f"MemoryPrunerDaemon started (interval: {self._interval_seconds}s, retain: {self._retain_seconds}s)")

    def stop(self) -> None:
        self._is_running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def _monitor_loop(self) -> None:
        time.sleep(60)
        while self._is_running:
            logger.info("MemoryPrunerDaemon: Running daily prune sweep...")
            try:
                run_sync(self._prune_and_vacuum())
            except Exception as e:
                logger.error(f"MemoryPrunerDaemon failed during prune cycle: {e}", exc_info=True)
            
            elapsed = 0.0
            while elapsed < self._interval_seconds and self._is_running:
                time.sleep(60)
                elapsed += 60

    async def _prune_and_vacuum(self) -> None:
        cutoff_time = time.time() - self._retain_seconds
        db = self._memory_store.store._conn() if hasattr(self._memory_store, "store") else self._memory_store._conn()
        
        cursor = await db.execute(
            "SELECT id, conversation_id, role, content FROM messages WHERE timestamp < ? ORDER BY conversation_id, timestamp ASC",
            (cutoff_time,)
        )
        rows = await cursor.fetchall()
        
        if not rows:
            logger.info("MemoryPrunerDaemon: No old messages to prune.")
        else:
            conversations = {}
            for row in rows:
                c_id = row["conversation_id"]
                if c_id not in conversations:
                    conversations[c_id] = []
                conversations[c_id].append(row)
            
            for c_id, msgs in conversations.items():
                if len(msgs) < 2:
                    continue

                logger.info(f"MemoryPrunerDaemon: Pruning {len(msgs)} old messages from conversation {c_id}")
                
                transcript = []
                msg_ids_to_delete = []
                for m in msgs:
                    role = m["role"].upper() if m["role"] else "UNKNOWN"
                    content = m["content"] or ""
                    transcript.append(f"{role}: {content}")
                    msg_ids_to_delete.append(m["id"])
                
                summary = "[Archived Context: No LLM available to summarize]"
                if self._llm:
                    prompt = (
                        "Summarize the following old chat messages into a single dense context block. "
                        "Focus on key facts, decisions, and important information. Keep it concise.\n\n" +
                        "\n".join(transcript)
                    )
                    messages = [{"role": "user", "content": prompt}]
                    response = None
                    try:
                        if hasattr(self._llm, "chat_with_tools"):
                            response_msg = await asyncio.to_thread(self._llm.chat_with_tools, messages, [], 60.0)
                            response = response_msg.get("content", "") if isinstance(response_msg, dict) else str(response_msg)
                        elif hasattr(self._llm, "chat"):
                            response = await asyncio.to_thread(self._llm.chat, messages, 60.0)
                        
                        if response:
                            summary = response.strip()
                    except Exception as e:
                        logger.error(f"MemoryPrunerDaemon: LLM summarization failed: {e}")
                
                sys_msg_id = uuid.uuid4().hex
                formatted_date = time.strftime("%Y-%m-%d", time.localtime(cutoff_time))
                sys_content = f"[Archived Context before {formatted_date}]\n{summary}"
                await db.execute(
                    "INSERT INTO messages (id, conversation_id, role, content, metadata_json, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                    (sys_msg_id, c_id, "system", sys_content, json.dumps({"pruned_messages": len(msgs)}), cutoff_time)
                )
                
                for chunk in [msg_ids_to_delete[i:i + 100] for i in range(0, len(msg_ids_to_delete), 100)]:
                    placeholders = ",".join("?" * len(chunk))
                    await db.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", chunk)
                
                await db.commit()
                logger.info(f"MemoryPrunerDaemon: Condensed {len(msgs)} messages into 1 for conversation {c_id}")
        
        logger.info("MemoryPrunerDaemon: Running VACUUM on database...")
        try:
            await db.execute("VACUUM")
            logger.info("MemoryPrunerDaemon: VACUUM completed successfully.")
        except Exception as e:
            logger.error(f"MemoryPrunerDaemon: VACUUM failed: {e}")
