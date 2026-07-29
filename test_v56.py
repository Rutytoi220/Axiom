import sys, os
sys.path.insert(0, os.getcwd())
import asyncio

async def test_all():
    # 1. Hierarchical Pager
    from axiom.engine.hierarchical_pager import ContextPagerService
    pager = ContextPagerService(max_l1_tokens=100)
    # 500 chars ~ 125 tokens > 100 limit, should trigger page out
    large_text_1 = "A" * 500
    pager.add_context(large_text_1)
    
    # Another 500 chars ~ 125 tokens
    large_text_2 = "B" * 500
    pager.add_context(large_text_2)
    
    stats = pager.get_stats()
    assert stats["L1_tokens"] <= 125  # Only the second chunk remains
    assert stats["L2_pages"] == 1    # First chunk got compressed
    print("Hierarchical Pager test passed")

    # 2. Cloud Burst Manager
    from axiom.engine.cloud_burst import CloudBurstManager
    cbm = CloudBurstManager()
    burst_success = await cbm.evaluate_capacity(local_utilization=0.98, task_queue_depth=100)
    assert burst_success == True
    nodes = cbm.get_active_nodes()
    assert len(nodes) > 0
    # Teardown
    for node_id in list(nodes.keys()):
        await cbm.teardown_node(node_id)
    assert len(cbm.get_active_nodes()) == 0
    print("Cloud Burst test passed")

    # 3. Wayland Compositor Hooks
    from axiom.gui.compositor_hook import WaylandOverlayInjector
    hook = WaylandOverlayInjector(compositor="gnome")
    # Should warn and return False since it's hardcoded to check for hyprland
    assert hook.highlight_window("terminal") == False
    assert hook.draw_floating_annotation("test", 0, 0) == True
    print("Wayland Hooks test passed")

    # 4. Infrastructure Topology Dialog
    from axiom.gui.widgets.infrastructure_dialog import InfrastructureTopologyDialog
    import PySide6.QtWidgets as QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    dlg = InfrastructureTopologyDialog()
    assert dlg.windowTitle() == "☁️ Infrastructure & Memory Topology"
    print("Infrastructure Dialog test passed")

if __name__ == "__main__":
    asyncio.run(test_all())
