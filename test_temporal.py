import asyncio
import logging
import time
from axiom.memory.schedules import ScheduleDatabase
from axiom.services.scheduler import TemporalService

logging.basicConfig(level=logging.INFO)

async def test_scheduler():
    # Insert a task that should run every minute
    db = ScheduleDatabase()
    await db.initialize()
    task_id = await db.add_schedule("Say hello", "* * * * *")
    print(f"Added task {task_id}")
    
    # Adjust last_run to ensure it triggers
    await db.update_last_run(task_id, time.time() - 61)
    
    svc = TemporalService()
    loop = asyncio.get_running_loop()
    
    svc.start(loop)
    print("Waiting 3 seconds for daemon to pick up task...")
    await asyncio.sleep(3)
    svc.stop()
    print("Test finished.")

if __name__ == "__main__":
    asyncio.run(test_scheduler())
