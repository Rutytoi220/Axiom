"""AXIOM Engine - Core orchestration and event handling."""

from typing import Optional, Any, Dict
import logging
import time
from axiom.core.events import EventBus, Event
from axiom.core.registry import Registry
from axiom.core.context import ExecutionContext

logger = logging.getLogger(__name__)


class Engine:
    """Main AXIOM orchestration engine."""
    
    def __init__(self, bus=None, registry=None, memory=None):
        self.event_bus = bus or EventBus()
        self.registry = registry or Registry()
        self.context: Optional[ExecutionContext] = None
        self._running = False
        self.started_at = None
        
        # Setup memory (use MemoryStore if not provided)
        if memory is None:
            from axiom.memory import SyncMemoryStore

            self.memory = SyncMemoryStore(":memory:")
        else:
            self.memory = memory
        
        self._setup_internal_handlers()
    
    def _setup_internal_handlers(self) -> None:
        """Setup internal event handlers."""
        self.event_bus.subscribe("error.handler", self._handle_error)
        self.event_bus.subscribe("system.shutdown", self._handle_shutdown)
    
    def _handle_error(self, event: Event) -> None:
        """Handle error events."""
        logger.error(f"Error in handler: {event.data.get('error')}")
    
    def _handle_shutdown(self, event: Event) -> None:
        """Handle shutdown events."""
        self._running = False
        logger.info("Engine shutdown initiated")
    
    def initialize(self) -> None:
        """Initialize the engine."""
        logger.info("Initializing AXIOM Engine")
        self._running = True
        self.started_at = time.time()
        
        # Log engine started event
        self.memory.log_event("engine.started", data={"started_at": self.started_at}, source="Engine")
        
        # Publish initialization event
        init_event = Event(
            event_type="system.initialized",
            source="Engine",
            data={"status": "ready"}
        )
        self.event_bus.publish(init_event)
    
    def create_context(self, user_input: str = "") -> ExecutionContext:
        """Create a new execution context."""
        self.context = ExecutionContext(user_input=user_input)
        return self.context
    
    def process(self, input_text: str) -> Any:
        """Process input through the engine."""
        if not self._running:
            raise RuntimeError("Engine is not running")
        
        # Create context
        self.context = self.create_context(input_text)
        
        # Publish input event
        input_event = Event(
            event_type="input.received",
            source="Engine",
            data={"input": input_text, "context_id": self.context.context_id}
        )
        self.event_bus.publish(input_event)
        
        return {
            "context_id": self.context.context_id,
            "status": "processing"
        }
    
    def get_current_context(self) -> Optional[ExecutionContext]:
        """Get current execution context."""
        return self.context
    
    def shutdown(self) -> None:
        """Shutdown the engine."""
        # Log engine stopped event
        self.memory.log_event("engine.stopped", data={"stopped_at": time.time()}, source="Engine")
        
        shutdown_event = Event(
            event_type="system.shutdown",
            source="Engine"
        )
        self.event_bus.publish(shutdown_event)
    
    def is_running(self) -> bool:
        """Check if engine is running."""
        return self._running

    def status(self) -> Dict[str, Any]:
        """Get engine status."""
        return {
            "running": self._running,
            "started_at": self.started_at,
            "event_count": len(self.memory.get_events())
        }

