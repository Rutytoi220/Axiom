import asyncio
import logging
from axiom.tools.base import axiom_tool, ToolResult
from axiom.memory.schedules import ScheduleDatabase

logger = logging.getLogger(__name__)

@axiom_tool(
    name="schedule_task",
    description="Schedules a natural language task to run at a specific time or interval using a cron expression.",
    parameters={
        "type": "object",
        "properties": {
            "natural_language_prompt": {
                "type": "string",
                "description": "The exact instruction or task to run, written as if speaking to the assistant (e.g. 'check system memory' or 'run health checks')"
            },
            "cron_schedule": {
                "type": "string",
                "description": "A standard 5-part cron expression defining when the task should run (e.g. '0 9 * * *' for 9 AM every day, '*/5 * * * *' for every 5 minutes)"
            }
        },
        "required": ["natural_language_prompt", "cron_schedule"]
    }
)
async def schedule_task(**kwargs) -> ToolResult:
    prompt = kwargs.get("natural_language_prompt")
    cron = kwargs.get("cron_schedule")
    
    if not prompt or not cron:
        return ToolResult(success=False, error="Missing prompt or cron schedule.")
        
    try:
        from croniter import croniter
        if not croniter.is_valid(cron):
            return ToolResult(success=False, error=f"Invalid cron expression: {cron}")
    except ImportError:
        pass
        
    try:
        db = ScheduleDatabase()
        await db.initialize()
        schedule_id = await db.add_schedule(prompt, cron)
        return ToolResult(
            success=True,
            output=f"Successfully scheduled task '{prompt}' with cron '{cron}'. Schedule ID: {schedule_id}"
        )
    except Exception as e:
        logger.error(f"Error scheduling task: {e}")
        return ToolResult(success=False, error=str(e))
