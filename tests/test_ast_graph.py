import pytest
from pathlib import Path
from axiom.indexer.graph_engine import CodeGraphIndex
from axiom.indexer.impact import get_dependent_files, get_inheritance_tree
from axiom.indexer.watcher import GraphWatcher
from axiom.core.events import EventBus

def test_ast_graph_indexing(tmp_path):
    # Setup mock workspace
    proj_dir = tmp_path / "project"
    proj_dir.mkdir()
    
    file_a = proj_dir / "a.py"
    file_a.write_text(
        "class BaseClass:\n"
        "    def hello(self):\n"
        "        pass\n"
        "def some_helper():\n"
        "    pass\n"
    )
    
    file_b = proj_dir / "b.py"
    file_b.write_text(
        "from a import BaseClass, some_helper\n"
        "class SubClass(BaseClass):\n"
        "    def do_work(self):\n"
        "        some_helper()\n"
        "        self.hello()\n"
    )
    
    # 1. Indexing
    index = CodeGraphIndex()
    index.index_workspace(proj_dir)
    
    # Verify graph nodes
    assert str(file_a) in index.graph
    assert str(file_b) in index.graph
    assert "BaseClass" in index.graph
    assert "SubClass" in index.graph
    assert "some_helper" in index.graph
    
    # Verify impact logic
    # some_helper is called in b.py's do_work, which means b.py depends on some_helper
    deps = get_dependent_files("some_helper", index)
    assert str(file_b) in deps
    assert str(file_a) not in deps  # file_a defines it, but doesn't call it (or does it? It defines it.)
    
    # Actually wait: get_dependent_files("BaseClass")
    # b.py defines SubClass which inherits BaseClass. So b.py depends on BaseClass
    deps_base = get_dependent_files("BaseClass", index)
    assert str(file_b) in deps_base
    
    # Inheritance Tree
    tree = get_inheritance_tree("BaseClass", index)
    assert "SubClass" in tree["children"]
    
    tree_sub = get_inheritance_tree("SubClass", index)
    assert "BaseClass" in tree_sub["parents"]

def test_graph_watcher_incremental_update(tmp_path):
    proj_dir = tmp_path / "project2"
    proj_dir.mkdir()
    
    file_a = proj_dir / "a.py"
    file_a.write_text("def my_func(): pass\n")
    
    index = CodeGraphIndex()
    index.index_workspace(proj_dir)
    assert "my_func" in index.graph
    
    bus = EventBus()
    watcher = GraphWatcher(bus, index)
    
    # Modify file_a to rename function
    file_a.write_text("def updated_func(): pass\n")
    
    # Emit transaction commit
    bus.publish_sync("transaction.committed", {
        "files_modified": [str(file_a)]
    })
    
    # Verify incremental update
    assert "my_func" not in index.graph
    assert "updated_func" in index.graph
