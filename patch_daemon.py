import sys

with open("axiom/server/daemon.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line == "from axiom.services.sys_watchdog import SystemHealthWatchdog\n":
        new_lines.append(line)
        new_lines.append("from axiom.memory.indexer import IndexerService\n")
    elif line == "        self.sys_watchdog = SystemHealthWatchdog(submit_task_callback=self._submit_task)\n":
        new_lines.append(line)
        new_lines.append("        \n")
        new_lines.append("        self.indexer_service = IndexerService(event_bus=self.event_bus)\n")
        new_lines.append("        self.indexer_service.start()\n")
    else:
        new_lines.append(line)

with open("axiom/server/daemon.py", "w") as f:
    f.writelines(new_lines)

