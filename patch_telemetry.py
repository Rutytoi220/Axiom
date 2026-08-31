import re

with open('axiom/services/telemetry_service.py', 'r') as f:
    content = f.read()

new_init = """    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._running = False
        self._task = None
        self._last_tick = time.time()
        
        # Capability Detection
        import shutil
        self._has_nvidia = shutil.which("nvidia-smi") is not None
        self._has_rocm = shutil.which("rocm-smi") is not None
"""

content = re.sub(r'    def __init__\(self, event_bus: EventBus\):\n.*?self\._last_tick = time\.time\(\)\n', new_init, content, flags=re.DOTALL)

gpu_logic = """                # Hardware Telemetry (GPU Agnostic)
                vram_percent = 0.0
                vram_mb = 0.0
                gpu_name = "Integrated / CPU-Only"
                
                import subprocess
                try:
                    if self._has_nvidia:
                        gpu_name = "Nvidia Discrete"
                        proc = subprocess.run(
                            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,nounits,noheader"],
                            capture_output=True, text=True, timeout=1.0
                        )
                        if proc.returncode == 0 and proc.stdout.strip():
                            used, total = map(float, proc.stdout.strip().split(",")[0:2])
                            vram_mb = used
                            vram_percent = (used / total) * 100 if total > 0 else 0
                    
                    elif self._has_rocm:
                        gpu_name = "AMD Discrete (ROCm)"
                        # rocm-smi output parsing (simplified)
                        proc = subprocess.run(
                            ["rocm-smi", "--showmeminfo", "vram", "--json"],
                            capture_output=True, text=True, timeout=1.0
                        )
                        if proc.returncode == 0 and proc.stdout.strip():
                            import json
                            data = json.loads(proc.stdout)
                            # rocm-smi returns e.g. {"card0": {"VRAM Total Memory (B)": "...", "VRAM Total Used Memory (B)": "..."}}
                            card = list(data.keys())[0]
                            if card != "system":
                                total_b = float(data[card].get("VRAM Total Memory (B)", 0))
                                used_b = float(data[card].get("VRAM Total Used Memory (B)", 0))
                                if total_b > 0:
                                    vram_mb = used_b / (1024 * 1024)
                                    vram_percent = (used_b / total_b) * 100
                
                except subprocess.TimeoutExpired:
                    logger.warning(f"GPU Telemetry timeout: {gpu_name}")
                except Exception as e:
                    logger.debug(f"GPU Telemetry error: {e}")
"""

content = re.sub(r'                # VRAM - Best effort \(NVIDIA\)\n.*?except Exception:\n                    pass\n', gpu_logic, content, flags=re.DOTALL)

payload_logic = """                payload = {
                    "cpu_percent": cpu_percent,
                    "ram_mb": ram_mb,
                    "ram_percent": ram_percent,
                    "vram_mb": vram_mb,
                    "vram_percent": vram_percent,
                    "gpu_name": gpu_name,
                    "active_tasks": active_tasks,
                    "loop_latency_ms": latency,
                    "mcp_servers_configured": mcp_servers
                }"""

content = re.sub(r'                payload = \{\n                    "cpu_percent": cpu_percent,.*?mcp_servers_configured": mcp_servers\n                \}', payload_logic, content, flags=re.DOTALL)

with open('axiom/services/telemetry_service.py', 'w') as f:
    f.write(content)

