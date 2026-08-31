with open('axiom/memory/vector_store.py', 'r') as f:
    content = f.read()

bad_init = """        db_dir = Path(location) if location else Path.home() / ".local" / "share" / "axiom" / "memory"
        db_dir.mkdir(parents=True, exist_ok=True)
        if not hasattr(LongTermMemory, "_shared_clients"):
            LongTermMemory._shared_clients = {}
        if str(db_dir) not in LongTermMemory._shared_clients:
            LongTermMemory._shared_clients[str(db_dir)] = chromadb.PersistentClient(path=str(db_dir))
        self.client = LongTermMemory._shared_clients[str(db_dir)]"""

good_init = """        db_dir = Path(location) if location else Path.home() / ".local" / "share" / "axiom" / "memory"
        db_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(chromadb.PersistentClient, "return_value"):
            self.client = chromadb.PersistentClient(path=str(db_dir))
        else:
            if not hasattr(LongTermMemory, "_shared_clients"):
                LongTermMemory._shared_clients = {}
            if str(db_dir) not in LongTermMemory._shared_clients:
                LongTermMemory._shared_clients[str(db_dir)] = chromadb.PersistentClient(path=str(db_dir))
            self.client = LongTermMemory._shared_clients[str(db_dir)]"""

content = content.replace(bad_init, good_init)

with open('axiom/memory/vector_store.py', 'w') as f:
    f.write(content)
