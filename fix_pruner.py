with open('axiom/memory/pruner.py', 'r') as f:
    content = f.read()

bad_start = """    def start(self) -> None:
        if self._is_running:
            return
        self._is_running = True
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._monitor_loop())
        logger.info("MemoryPrunerDaemon started (interval: 3600s)")"""

good_start = """    def start(self) -> None:
        if self._is_running:
            return
        self._is_running = True
        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._monitor_loop())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._task = loop.create_task(self._monitor_loop())
        logger.info("MemoryPrunerDaemon started (interval: 3600s)")"""

content = content.replace(bad_start, good_start)
with open('axiom/memory/pruner.py', 'w') as f:
    f.write(content)
