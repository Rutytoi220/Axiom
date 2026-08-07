import os
import time
import logging
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

try:
    import chromadb
except ImportError:
    chromadb = None

logger = logging.getLogger("axiom.memory.indexer")

class AxiomFSHandler(FileSystemEventHandler):
    def __init__(self, indexer_service):
        self.indexer = indexer_service

    def on_modified(self, event):
        if event.is_directory:
            return
        self.indexer.queue_file(event.src_path)

    def on_created(self, event):
        if event.is_directory:
            return
        self.indexer.queue_file(event.src_path)


class IndexerService:
    """Background Daemon for AxiomFS that indexes local files into ChromaDB."""
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.workspace_dir = Path.home() / ".local" / "share" / "axiom" / "workspace"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_dir = Path.home() / ".local" / "share" / "axiom" / "chromadb"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        
        self._running = False
        self._thread = None
        self._observer = None
        
        self.client = None
        self.collection = None
        
        self._queue = set()
        self._queue_lock = threading.Lock()
        
    def start(self):
        if self._running or not chromadb:
            if not chromadb:
                logger.error("ChromaDB not installed. AxiomFS cannot start.")
            return
            
        self.client = chromadb.PersistentClient(path=str(self.db_dir))
        self.collection = self.client.get_or_create_collection(name="axiom_fs")
        
        self._running = True
        self._thread = threading.Thread(target=self._process_queue, daemon=True)
        self._thread.start()
        
        self._observer = Observer()
        handler = AxiomFSHandler(self)
        self._observer.schedule(handler, str(self.workspace_dir), recursive=True)
        self._observer.start()
        
        logger.info("[AxiomFS] Started Indexer Daemon.")
        self._emit_status("Idle")
        
    def stop(self):
        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join()
            
    def queue_file(self, file_path: str):
        if file_path.endswith((".txt", ".md", ".py")):
            with self._queue_lock:
                self._queue.add(file_path)
                
    def _emit_status(self, status: str):
        if self.event_bus:
            from axiom.core.events import Event
            try:
                self.event_bus.publish(Event(event_type="axiomfs.status", source="IndexerService", data={"status": status}))
            except Exception:
                pass

    def _process_queue(self):
        while self._running:
            files_to_process = []
            with self._queue_lock:
                if self._queue:
                    files_to_process = list(self._queue)
                    self._queue.clear()
                    
            if files_to_process:
                self._emit_status("Indexing...")
                for file_path in files_to_process:
                    self._index_file(file_path)
                self._emit_status("Idle")
                
            time.sleep(2)
            
    def _index_file(self, file_path: str):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Basic overlapping chunker
            chunk_size = 1000
            overlap = 200
            chunks = []
            for i in range(0, len(content), chunk_size - overlap):
                chunks.append(content[i:i + chunk_size])
                
            if not chunks:
                return
                
            # Remove old entries for this file
            try:
                self.collection.delete(where={"file_path": file_path})
            except Exception:
                pass
                
            ids = [f"{file_path}_{i}" for i in range(len(chunks))]
            metadatas = [{"file_path": file_path, "chunk": i} for i in range(len(chunks))]
            
            self.collection.add(
                documents=chunks,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"[AxiomFS] Indexed {file_path} ({len(chunks)} chunks)")
        except Exception as e:
            logger.error(f"[AxiomFS] Failed to index {file_path}: {e}")
