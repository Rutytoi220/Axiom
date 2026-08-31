import os
import time
import logging
import threading
import asyncio
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger("axiom.memory.indexer")

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}
IGNORE_EXTS = {".AppImage", ".deb", ".pyc", ".whl"}

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
    """Background Daemon for AxiomFS that indexes local files async."""
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.workspace_dir = Path.home() / ".local" / "share" / "axiom" / "workspace"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = Path.home() / ".axiom" / "memory.db"
        
        self._running = False
        self._task = None
        self._observer = None
        
        self._queue = set()
        self._queue_lock = threading.Lock()
        
    def start(self):
        if self._running:
            return
            
        self._running = True
        self._task = asyncio.create_task(self._process_queue_async())
        
        self._observer = Observer()
        handler = AxiomFSHandler(self)
        self._observer.schedule(handler, str(self.workspace_dir), recursive=True)
        self._observer.start()
        
        logger.info("[AxiomFS] Started Async Indexer Daemon.")
        self._emit_status("Idle")
        
    def stop(self):
        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join()
        if self._task:
            self._task.cancel()
            
    def queue_file(self, file_path: str):
        if any(ignored in Path(file_path).parts for ignored in IGNORE_DIRS):
            return
        if any(file_path.endswith(ext) for ext in IGNORE_EXTS):
            return
            
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

    async def _read_file_async(self, file_path: str) -> str:
        def _read():
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        return await asyncio.to_thread(_read)

    async def _process_queue_async(self):
        from axiom.memory.semantic import SemanticIndex
        from axiom.llm.universal_client import UniversalLLMClient
        from axiom.config import get_config
        import aiosqlite
        
        try:
            config = get_config()
            llm = UniversalLLMClient(default_model=config.ollama_model)
            semantic = SemanticIndex(provider=llm, event_bus=self.event_bus)
        except Exception as e:
            logger.error(f"[AxiomFS] Failed to initialize semantic indexing: {e}")
            return
            
        db = None
        while self._running:
            try:
                files_to_process = []
                with self._queue_lock:
                    if self._queue:
                        files_to_process = list(self._queue)
                        self._queue.clear()
                        
                if files_to_process:
                    if db is None:
                        from axiom.memory.db import MemoryDatabaseManager
                        db_mgr = await MemoryDatabaseManager.get_instance(self.db_path)
                        db = await db_mgr.get_connection()
                    
                    self._emit_status("Indexing...")
                    
                    for file_path in files_to_process:
                        if not os.path.exists(file_path):
                            continue
                            
                        content = await self._read_file_async(file_path)
                        await asyncio.sleep(0)
                        
                        chunk_size = 1000
                        overlap = 200
                        chunks = []
                        for i in range(0, len(content), chunk_size - overlap):
                            chunks.append(content[i:i + chunk_size])
                            
                        if not chunks:
                            continue
                            
                        batch_size = 8
                        for i in range(0, len(chunks), batch_size):
                            batch = chunks[i:i+batch_size]
                            items = []
                            for j, text in enumerate(batch):
                                items.append({
                                    "owner_id": f"{file_path}_{i+j}",
                                    "owner_type": "fs_file",
                                    "text": text
                                })
                            
                            success = await semantic.store_texts_batch(db, items, model=config.ollama_model)
                            if not success:
                                logger.warning("[AxiomFS] Embedding provider unavailable. Skipping semantic batch for now.")
                            await asyncio.sleep(0)
                            
                        logger.info(f"[AxiomFS] Indexed {file_path} ({len(chunks)} chunks)")
                    
                    self._emit_status("Idle")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"ERROR: {e}"); logger.error(f"[AxiomFS] Indexing error: {e}")
                
            await asyncio.sleep(0.5)
            
        if db:
            await db.close()

