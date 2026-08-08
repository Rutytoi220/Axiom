import sys

with open("axiom/memory/vector_store.py", "r") as f:
    text = f.read()

# I need to find where self.embedding_model is set in ChromaStore and QdrantStore
# Let's replace hardcoded 'ollama/nomic-embed-text' and 'nomic-embed-text:latest'

# For QdrantLocalStore:
# self.embedding_model = 'ollama/nomic-embed-text'
# self._ensure_embedding_model()

# We need to dynamically get the installed models first.

# Let's write a python replacement snippet.
old_ensure = """        self.embedding_model = 'ollama/nomic-embed-text'
        self._ensure_embedding_model()"""

new_ensure = """        self.embedding_model = self._find_embedding_model()
        
    def _find_embedding_model(self) -> str:
        import httpx
        try:
            r = httpx.get('http://127.0.0.1:11434/api/tags', timeout=2.0)
            if r.status_code == 200:
                models = [m['name'] for m in r.json().get('models', [])]
                for m in models:
                    if 'embed' in m.lower():
                        return f'ollama/{m}'
                if models:
                    return f'ollama/{models[0]}'
        except Exception:
            pass
        return 'ollama/nomic-embed-text'
"""

text = text.replace(old_ensure, new_ensure)

old_chroma = """        self.embedding_url = "http://localhost:11434/api/embeddings"
        self.embedding_model = "nomic-embed-text:latest\""""

new_chroma = """        self.embedding_url = "http://127.0.0.1:11434/api/embeddings"
        self.embedding_model = self._find_embedding_model()

    def _find_embedding_model(self) -> str:
        import httpx
        try:
            r = httpx.get('http://127.0.0.1:11434/api/tags', timeout=2.0)
            if r.status_code == 200:
                models = [m['name'] for m in r.json().get('models', [])]
                for m in models:
                    if 'embed' in m.lower():
                        return m
                if models:
                    return models[0]
        except Exception:
            pass
        return "nomic-embed-text:latest\""""

text = text.replace(old_chroma, new_chroma)

with open("axiom/memory/vector_store.py", "w") as f:
    f.write(text)

