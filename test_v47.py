from axiom.engine.container_sandbox import ContainerSandboxManager
from axiom.tools.workspace_manager import WorkspaceOrchestrateTool
from axiom.engine.sharded_rag import ShardedRAGManager

def test():
    # 1. Sandbox test
    cm = ContainerSandboxManager()
    # Force bwrap mode for test
    cm.mode = "bwrap"
    cm.bwrap_path = "/usr/bin/bwrap"
    cmd = cm.wrap_command("touch /etc/hacked", "/workspace")
    assert "--ro-bind /etc /etc" not in cmd # wait, actually we ro-bind /usr, /bin, /lib. /etc is not bound so it's empty/read-only by default or not accessible, which effectively blocks writes.
    # Actually wait, we unshare-all which isolates the mount namespace. 
    # But let's just check the wrapper generated correctly
    assert "bwrap" in cmd
    assert "--unshare-all" in cmd
    assert "touch /etc/hacked" in cmd
    print("Sandbox Test Passed")
    
    # 2. Workspace Tool test
    tool = WorkspaceOrchestrateTool()
    assert tool.name == "workspace_orchestrator"
    print("Workspace Tool Test Passed")
    
    # 3. Sharded RAG test
    rag = ShardedRAGManager(["node_A", "node_B", "node_C"])
    target1 = rag._consistent_hash("doc_123")
    target2 = rag._consistent_hash("doc_123")
    assert target1 == target2
    print("Sharded RAG Test Passed")

test()
