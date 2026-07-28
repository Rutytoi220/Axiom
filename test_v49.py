from axiom.engine.vm_orchestrator import MicroVMManager
from axiom.services.auto_upgrader import CICDUpgraderService
import asyncio

async def test():
    # 1. VM Orchestrator
    vm_mgr = MicroVMManager()
    vm_id = vm_mgr.create_disposable_vm()
    assert vm_id in vm_mgr.active_vms
    output = vm_mgr.exec_in_vm(vm_id, "echo test")
    assert output is not None
    vm_mgr.destroy_vm(vm_id)
    assert vm_id not in vm_mgr.active_vms
    print("VM Orchestrator Test Passed")
    
    # 2. CI/CD Upgrader
    upgrader = CICDUpgraderService()
    res = await upgrader.execute_self_upgrade()
    assert res is True
    print("CI/CD Upgrader Test Passed")

asyncio.run(test())
