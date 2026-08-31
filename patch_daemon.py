import sys

def patch_file():
    with open('axiom/server/daemon.py', 'r') as f:
        content = f.read()
        
    init_new = """    def __init__(self):
        from axiom.core.events import EventBus
        self.event_bus = EventBus()
        self.cli = None
        
        self.scheduler_service = None
        self.telemetry = None
        self.governor = None
        self.swarm_router = None
        self.sys_watchdog = None
        self.governor_service = None
        self.indexer_service = None
        
        from axiom.services.watchdog_service import DirectoryWatchdog
        self.dir_watchdog = DirectoryWatchdog()
        self.clients = set()
        self.event_bus.subscribe("*", self._on_bus_event)"""
        
    import re
    content = re.sub(r'    def __init__\(self\):.*?self\.event_bus\.subscribe\("\*", self\._on_bus_event\)', init_new, content, flags=re.DOTALL)
    
    init_bg = """    async def initialize_background(self):
        from axiom.core.lifecycle import LifecycleState
        from axiom.core.events import Event
        
        def _emit_status(service_name, state):
            self.event_bus.publish_sync("startup.service.update", {"service": service_name, "state": state})

        _emit_status("core", LifecycleState.CORE_INITIALIZING)
        
        # Heavy CLI Init
        from axiom.api.cli import CLI
        self.cli = CLI(bus=self.event_bus)
        _emit_status("core", LifecycleState.READY)"""
        
    content = re.sub(r'    async def initialize_background\(self\):.*?def _emit_status\(service_name, state\):.*?self\.event_bus\.publish_sync\("startup\.service\.update", {"service": service_name, "state": state}\)', init_bg, content, flags=re.DOTALL)
    
    # We also need to handle cases where self.cli is None in handle_client!
    # Wait, in handle_client, if self.cli is None, it should reply "Service Starting..." or similar.
    # Actually, we can just replace self.cli calls with a check. Let's patch handle_client.
    
    with open('axiom/server/daemon.py', 'w') as f:
        f.write(content)

patch_file()
