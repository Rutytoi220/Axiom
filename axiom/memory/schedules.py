import asyncio
import logging
import uuid
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

import aiosqlite

logger = logging.getLogger(__name__)

class ScheduleDatabase:
    """Async SQLite database for tracking scheduled AI tasks."""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            data_dir = Path.home() / ".local" / "share" / "axiom"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(data_dir / "schedules.db")
        else:
            self.db_path = db_path

    async def initialize(self) -> None:
        """Create the schedules table if it doesn't exist."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schedules (
                        id TEXT PRIMARY KEY,
                        user_prompt TEXT,
                        cron_expression TEXT,
                        last_run REAL,
                        is_active INTEGER
                    )
                    """
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to initialize ScheduleDatabase: {e}")

    async def add_schedule(self, user_prompt: str, cron_expression: str) -> str:
        """Create a new schedule and return its ID."""
        schedule_id = str(uuid.uuid4())
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO schedules (id, user_prompt, cron_expression, last_run, is_active) VALUES (?, ?, ?, ?, ?)",
                    (schedule_id, user_prompt, cron_expression, 0.0, 1)
                )
                await db.commit()
            return schedule_id
        except Exception as e:
            logger.error(f"Failed to create schedule: {e}")
            return schedule_id

    async def get_schedules(self) -> List[Dict[str, Any]]:
        """Retrieve all schedules."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM schedules") as cursor:
                    rows = await cursor.fetchall()
                    return [
                        {
                            "id": row["id"],
                            "user_prompt": row["user_prompt"],
                            "cron_expression": row["cron_expression"],
                            "last_run": row["last_run"],
                            "is_active": bool(row["is_active"])
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Failed to get schedules: {e}")
            return []

    async def update_last_run(self, schedule_id: str, timestamp: float) -> None:
        """Update the last_run timestamp for a schedule."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE schedules SET last_run = ? WHERE id = ?",
                    (timestamp, schedule_id)
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to update last_run for {schedule_id}: {e}")

    async def toggle_schedule(self, schedule_id: str, is_active: bool) -> None:
        """Toggle a schedule active or inactive."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE schedules SET is_active = ? WHERE id = ?",
                    (1 if is_active else 0, schedule_id)
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to toggle schedule {schedule_id}: {e}")

    async def delete_schedule(self, schedule_id: str) -> None:
        """Delete a schedule."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM schedules WHERE id = ?",
                    (schedule_id,)
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to delete schedule {schedule_id}: {e}")
