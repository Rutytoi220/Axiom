from axiom.fs.axiom_fs import AxiomFS
from axiom.tools.live_vision import LiveVisionStreamTool
from axiom.services.thermal_governor import ThermalGovernorService
import asyncio

def test():
    # 1. AxiomFS
    fs = AxiomFS()
    root_files = list(fs.readdir("/", None))
    assert "by-concept" in root_files
    assert "by-service" in root_files
    
    sub_files = list(fs.readdir("/by-concept", None))
    assert "docker" in sub_files
    print("AxiomFS Test Passed")
    
    # 2. Live Vision
    tool = LiveVisionStreamTool()
    assert tool.name == "live_vision_stream"
    print("Live Vision Tool Test Passed")
    
    # 3. Thermal Governor
    gov = ThermalGovernorService()
    gov._evaluate_thermals(64.0)
    assert gov.current_state == "Normal"
    gov._evaluate_thermals(78.0)
    assert gov.current_state == "Warning"
    gov._evaluate_thermals(92.0)
    assert gov.current_state == "Critical"
    print("Thermal Governor Test Passed")

test()
