import time
from datetime import datetime
from croniter import croniter

now = time.time()
last_run = now - 120

base_time = datetime.fromtimestamp(last_run)
cron = croniter("* * * * *", base_time)
next_run = cron.get_next(float)

print(f"now: {now}")
print(f"last_run: {last_run}")
print(f"base_time: {base_time}")
print(f"next_run: {next_run}")
print(f"now >= next_run: {now >= next_run}")
