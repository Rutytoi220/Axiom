import time
from croniter import croniter

now = time.time()
last_run = now - 120

cron = croniter("* * * * *", last_run)
next_run = cron.get_next(float)

print(f"now: {now}")
print(f"last_run: {last_run}")
print(f"next_run: {next_run}")
print(f"now >= next_run: {now >= next_run}")
