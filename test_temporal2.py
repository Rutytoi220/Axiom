import asyncio
import logging
import time
from axiom.memory.schedules import ScheduleDatabase
from axiom.services.scheduler import TemporalService

logging.basicConfig(level=logging.INFO)

async def test_scheduler():
    db = ScheduleDatabase()
    await db.initialize()
    task_id = await db.add_schedule("Say hello", "* * * * *")
    print(f"Added task {task_id}")
    
    await db.update_last_run(task_id, time.time() - 120)
    schedules = await db.get_schedules()
    print("Schedules in DB:", schedules)
    
    svc = TemporalService()
    loop = asyncio.get_running_loop()
    
    svc.start(loop)
    await asyncio.sleep(2)
    svc.stop()

if __name__ == "__main__":
    asyncio.run(test_scheduler())
