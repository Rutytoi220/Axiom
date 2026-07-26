import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from axiom.core.transaction import WorkspaceTransactionManager, StagingCapExceeded, _NEW_FILE_SENTINEL

@pytest.fixture
def manager(tmp_path):
    bus = MagicMock()
    return WorkspaceTransactionManager(bus=bus, staging_root=tmp_path / "staging")

def test_begin_commit(manager):
    assert manager.is_active == False
    manager.begin()
    assert manager.is_active == True
    manager.begin() # coverage for already active
    
    manager.commit()
    assert manager.is_active == False
    manager.commit() # coverage for not active

def test_rollback(manager, tmp_path):
    manager.begin()
    manager.rollback() # nothing to rollback
    
    manager.begin()
    target = tmp_path / "test.txt"
    target.write_text("orig")
    manager.snapshot(target)
    
    # modify
    target.write_text("mutated")
    
    manager.rollback()
    assert target.read_text() == "orig"
    
def test_rollback_new_file(manager, tmp_path):
    manager.begin()
    target = tmp_path / "new.txt"
    manager.snapshot(target) # should register as new file
    
    target.write_text("created")
    manager.rollback()
    assert not target.exists()
    
def test_rollback_missing_backup(manager, tmp_path):
    manager.begin()
    target = tmp_path / "test2.txt"
    target.write_text("orig2")
    manager.snapshot(target)
    
    # delete backup
    key = str(target.resolve())
    backup_path = Path(manager._snapshots[key])
    backup_path.unlink()
    
    manager.rollback()

def test_rollback_error(manager, tmp_path):
    manager.begin()
    target = tmp_path / "test3.txt"
    target.write_text("orig3")
    manager.snapshot(target)
    
    with patch("shutil.copy2", side_effect=Exception("error")):
        manager.rollback()

def test_purge_blackboard(tmp_path):
    bb = MagicMock()
    manager = WorkspaceTransactionManager(blackboard=bb, session_id="123", staging_root=tmp_path / "staging")
    manager.begin()
    manager.commit()
    bb.purge_session.assert_called_with("123")
    
def test_snapshot_exceptions(manager, tmp_path):
    with pytest.raises(RuntimeError):
        manager.snapshot("file.txt")
        
    manager.begin()
    target = tmp_path / "large.txt"
    target.write_text("x" * (50 * 1024 * 1024 + 10))
    with pytest.raises(StagingCapExceeded):
        manager.snapshot(target)
        
    target2 = tmp_path / "err.txt"
    target2.write_text("test")
    with patch("shutil.copy2", side_effect=Exception("err")):
        with pytest.raises(RuntimeError):
            manager.snapshot(target2)

def test_should_snapshot(manager):
    assert manager.should_snapshot("write_file") == True
    assert manager.should_snapshot("read_file") == False

def test_context_manager(tmp_path):
    with WorkspaceTransactionManager(staging_root=tmp_path / "staging") as m:
        assert m.is_active
    assert not m.is_active
    
    with pytest.raises(ValueError):
        with WorkspaceTransactionManager(staging_root=tmp_path / "staging") as m:
            raise ValueError("error")

def test_failure_event(manager):
    manager.begin()
    event = MagicMock()
    event.event_type = "plan.failed"
    event.data = {"step": 1, "total_steps": 2}
    manager._on_failure_event(event)
    assert not manager.is_active

    manager._on_failure_event(event) # inactive
    
def test_unsubscribe_error(manager):
    manager._bus.unsubscribe.side_effect = Exception("error")
    manager._unsubscribe_failure_events()

def test_properties(manager):
    assert manager.transaction_id is not None
    assert manager.snapshot_count == 0

def test_cleanup_error(manager):
    manager.begin()
    with patch("shutil.rmtree", side_effect=Exception("error")):
        manager._cleanup_staging()
