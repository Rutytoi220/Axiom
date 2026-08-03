"""Hardware Telemetry Engine.

Monitors CPU, RAM, and GPU resources and broadcasts snapshots over the EventBus.
Fails gracefully if hardware-specific libraries (like pynvml) are unavailable.
"""

import asyncio
import logging
import psutil
from typing import Any, Dict

from axiom.core.events import EventBus

logger = logging.getLogger(__name__)

class TelemetryDaemon:
    """Background task that polls system metrics and emits updates."""

    def __init__(self, event_bus: EventBus, poll_interval: float = 1.5):
        self.bus = event_bus
        self.poll_interval = poll_interval
        self._is_running = False
        self._task: asyncio.Task | None = None
        self._nvml_initialized = False

        # Attempt to initialize NVML for NVIDIA GPUs
        try:
            import pynvml
            pynvml.nvmlInit()
            self._nvml_initialized = True
            self.gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            logger.info("TelemetryDaemon: NVML initialized successfully.")
        except ImportError:
            logger.warning("TelemetryDaemon: pynvml not installed. GPU stats will be N/A.")
        except Exception as e:
            logger.warning(f"TelemetryDaemon: NVML initialization failed: {e}. GPU stats will be N/A.")

    def start(self) -> None:
        """Start the background polling loop."""
        if self._is_running:
            return
        self._is_running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"TelemetryDaemon started (interval: {self.poll_interval}s)")

    def stop(self) -> None:
        """Stop the background polling loop."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            
        if self._nvml_initialized:
            try:
                import pynvml
                pynvml.nvmlShutdown()
            except Exception:
                pass

    async def _monitor_loop(self) -> None:
        while self._is_running:
            try:
                snapshot = self._gather_metrics()
                self.bus.publish_sync("telemetry.update", snapshot)
            except Exception as e:
                logger.error(f"TelemetryDaemon tick failed: {e}", exc_info=True)
            
            await asyncio.sleep(self.poll_interval)

    def _gather_metrics(self) -> Dict[str, Any]:
        """Collect current system metrics."""
        cpu_percent = psutil.cpu_percent(interval=None)
        
        # We can also get CPU temp if supported by OS, fallback to -1
        cpu_temp = -1.0
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                # Prioritize known CPU temp sensors over random ACPI zones
                if 'coretemp' in temps and temps['coretemp']:
                    cpu_temp = temps['coretemp'][0].current
                elif 'k10temp' in temps and temps['k10temp']:
                    cpu_temp = temps['k10temp'][0].current
                else:
                    for name, entries in temps.items():
                        if entries:
                            cpu_temp = entries[0].current
                            break
        except Exception:
            pass

        ram = psutil.virtual_memory()
        ram_percent = ram.percent

        gpu_temp = -1.0
        vram_percent = -1.0
        
        if self._nvml_initialized:
            import pynvml
            try:
                gpu_temp = float(pynvml.nvmlDeviceGetTemperature(self.gpu_handle, pynvml.NVML_TEMPERATURE_GPU))
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
                vram_percent = (mem_info.used / mem_info.total) * 100.0
            except Exception:
                pass

        # Build snapshot. model and auth_mode are injected by the orchestrator elsewhere, 
        # but we provide the hardware baseline here.
        return {
            "cpu": cpu_percent,
            "cpu_temp": cpu_temp,
            "ram": ram_percent,
            "gpu_temp": gpu_temp,
            "vram": vram_percent
        }
