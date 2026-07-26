import pytest
import os
from pathlib import Path
from axiom.indexer.graph_engine import CodeGraphIndex
from axiom.indexer.watcher import GraphWatcher


def test_indexer_graph_engine_import_attribute_async_errors(tmp_path):
    index = CodeGraphIndex()
    # test file 1: normal, import, async, class inheritance with attribute
    f1 = tmp_path / "f1.py"
    f1.write_text("""
import math
class MyClass(math.MathBase):
    async def my_async_func(self):
        pass
""")
    index.update_file(f1)
    
    assert "math" in index.graph
    assert "MyClass" in index.graph
    assert "MyClass.my_async_func" in index.graph

def test_indexer_graph_engine_missing_file(tmp_path):
    index = CodeGraphIndex()
    missing = tmp_path / "missing.py"
    index.update_file(missing) # should just return

def test_indexer_graph_engine_syntax_error(tmp_path):
    index = CodeGraphIndex()
    bad = tmp_path / "bad.py"
    bad.write_text("def class )() : :")
    index.update_file(bad) # should catch SyntaxError

def test_indexer_graph_engine_other_error(tmp_path, monkeypatch):
    index = CodeGraphIndex()
    bad = tmp_path / "bad.py"
    bad.write_text("a=1")
    def mock_read(*args, **kwargs):
        raise OSError("denied")
    monkeypatch.setattr(Path, "read_text", mock_read)
    index.update_file(bad) # should catch Exception

def test_dependency_analyzer(tmp_path):
    from axiom.indexer.graph_engine import CodeGraphIndex
    from axiom.indexer.impact import get_dependent_files, get_inheritance_tree
    
    index = CodeGraphIndex()
    
    # Line 12
    assert get_dependent_files("missing_sym", index) == []
    
    # Line 45
    assert get_inheritance_tree("missing_class", index) == {"class": "missing_class", "parents": [], "children": []}
    
    # Lines 22-23 (file imports module)
    f1 = tmp_path / "f1.py"
    f1.write_text("import my_mod")
    index.update_file(f1)
    
    assert str(f1) in get_dependent_files("my_mod", index)


def test_workspace_watcher(tmp_path):
    from axiom.indexer.watcher import GraphWatcher
    from axiom.core.events import EventBus, Event
    from axiom.indexer.graph_engine import CodeGraphIndex
    bus = EventBus()
    index = CodeGraphIndex()
    watcher = GraphWatcher(bus, index)
    
    # Empty files modified (Line 31)
    ev = Event(event_type="transaction.committed", source="src", data={"files_modified": []})
    ev.type = "transaction.committed" # for backward compatibility or mock
    watcher._on_transaction_end(ev)
    
    # Normal files modified
    ev2 = Event(event_type="transaction.committed", source="src", data={"files_modified": ["test.py"]})
    ev2.type = "transaction.committed"
    watcher._on_transaction_end(ev2)

