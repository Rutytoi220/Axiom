import sys, os
sys.path.insert(0, os.getcwd())
import asyncio

async def test_all():
    # 1. REM Sleep Deduplication
    from axiom.memory.rem_sleep import DeepMemoryConsolidation
    from axiom.core.events import EventBus
    eb = EventBus()
    dmc = DeepMemoryConsolidation(eb)
    mock_graph = [
        "Duplicate string A",
        "Unique string B",
        "DUPLICATE string a",
        "Duplicate string A "
    ]
    fused = await dmc.trigger_rem_sleep(mock_graph)
    assert len(fused) == 2
    print("REM Sleep test passed")

    # 2. Network Assimilation
    from axiom.server.mesh_deployer import SwarmAssimilatorTool
    tool = SwarmAssimilatorTool()
    res = await tool.assimilate_node("root@127.0.0.1")
    assert res["status"] == "success"
    assert res["architecture"] == "x86_64"
    assert "package_deployed" in res
    print("Network Assimilation test passed")

    # 3. RLHF Engine
    from axiom.engine.self_improvement import RLHFEngine
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = RLHFEngine(data_dir=tmpdir)
        await engine.run_synthetic_loop()
        assert os.path.exists(os.path.join(tmpdir, "rlhf_preferences.jsonl"))
        
        modelfile = engine.evolve_model()
        assert os.path.exists(modelfile)
        with open(modelfile, "r") as f:
            content = f.read()
            assert "FROM llama3:8b" in content
            assert "You are AXIOM-CORE" in content
            
    print("RLHF Engine test passed")

    # 4. Singularity UI
    from axiom.gui.widgets.singularity_dialog import SingularityControlDialog
    import PySide6.QtWidgets as QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    dlg = SingularityControlDialog(None, eb)
    assert dlg.windowTitle() == "🌌 Singularity Engine"
    print("Singularity Dialog test passed")

if __name__ == "__main__":
    asyncio.run(test_all())
