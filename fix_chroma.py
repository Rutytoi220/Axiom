with open('axiom/memory/vector_store.py', 'r') as f:
    content = f.read()

bad_init = """        db_dir = Path(location) if location else Path.home() / ".local" / "share" / "axiom" / "memory"
        db_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(db_dir))
        self.collection = self.client.get_or_create_collection(
            name="axiom_hippocampus",
            metadata={"hnsw:space": "cosine"}
        )"""

good_init = """        db_dir = Path(location) if location else Path.home() / ".local" / "share" / "axiom" / "memory"
        db_dir.mkdir(parents=True, exist_ok=True)
        if not hasattr(LongTermMemory, "_shared_client"):
            LongTermMemory._shared_client = chromadb.PersistentClient(path=str(db_dir))
        self.client = LongTermMemory._shared_client
        self.collection = self.client.get_or_create_collection(
            name="axiom_hippocampus",
            metadata={"hnsw:space": "cosine"}
        )"""

content = content.replace(bad_init, good_init)

with open('axiom/memory/vector_store.py', 'w') as f:
    f.write(content)
