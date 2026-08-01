"""Thermal Governor.

Listens to hardware telemetry and emits throttle events to protect system stability
when temperatures or VRAM usage exceed configured limits.
"""

import logging
from typing import Any

from axiom.core.events import EventBus

logger = logging.getLogger(__name__)

class ThermalGovernor:
    """Singleton that monitors telemetry and emits throttling signals."""

    _instance = None

    @classmethod
    def instance(cls, event_bus: EventBus = None):
        if cls._instance is None:
            if event_bus is None:
                raise ValueError("event_bus must be provided on first initialization.")
            cls._instance = cls(event_bus)
        return cls._instance

    def __init__(self, event_bus: EventBus):
        if ThermalGovernor._instance is not None:
            raise RuntimeError("ThermalGovernor is a singleton. Use .instance().")
            
        self.bus = event_bus
        self.bus.subscribe("telemetry.update", self._on_telemetry)
        
        # Thresholds
        self.max_cpu_temp = 90.0
        self.max_gpu_temp = 90.0
        self.max_vram_usage = 95.0
        
        # State
        self.is_throttled = False
        
        logger.info("ThermalGovernor initialized.")

    def _on_telemetry(self, event: Any) -> None:
        """Evaluate hardware telemetry and trigger limits if breached."""
        data = getattr(event, "data", {})
        
        cpu_temp = data.get("cpu_temp", -1.0)
        gpu_temp = data.get("gpu_temp", -1.0)
        vram = data.get("vram", -1.0)
        
        breach_reasons = []
        
        if cpu_temp > self.max_cpu_temp:
            breach_reasons.append(f"CPU Temp Critical ({cpu_temp:.1f}C)")
            
        if gpu_temp > self.max_gpu_temp:
            breach_reasons.append(f"GPU Temp Critical ({gpu_temp:.1f}C)")
            
        if vram > self.max_vram_usage:
            breach_reasons.append(f"VRAM Capacity Critical ({vram:.1f}%)")

        if breach_reasons:
            if not self.is_throttled:
                logger.warning(f"ThermalGovernor: Throttling engaged! {', '.join(breach_reasons)}")
                self.is_throttled = True
                self.bus.publish_sync("system.throttle", {"active": True, "reasons": breach_reasons})
        else:
            if self.is_throttled:
                # Add hysteresis logic here in the future if needed
                logger.info("ThermalGovernor: Operating parameters nominal. Throttling disengaged.")
                self.is_throttled = False
                self.bus.publish_sync("system.throttle", {"active": False, "reasons": []})
