import asyncio
from axiom.core.events import EventBus
from axiom.services.kernel_watchdog import KernelWatchdogService

class MockEventBus(EventBus):
    def publish_sync(self, topic, data):
        print(f"MockEventBus Intercepted: {topic} -> {data}")

bus = MockEventBus()
watchdog = KernelWatchdogService(bus)
watchdog._analyze_entry({
    "MESSAGE": "process 1234 (bash) segfault at 0 ip 12345 sp 12345 error 4 in libreadline.so.8.1",
    "_SYSTEMD_UNIT": "session-1.scope"
})

watchdog._analyze_entry({
    "MESSAGE": "docker.service: Failed with result 'exit-code'.",
    "_SYSTEMD_UNIT": "docker.service"
})
