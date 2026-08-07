import logging
from pathlib import Path
from axiom.tools.plugin_loader import axiom_tool

logger = logging.getLogger("axiom.tools.search_plugins")

try:
    import chromadb
except ImportError:
    chromadb = None

@axiom_tool(
    name="semantic_file_search",
    description="Search the local file system (AxiomFS) for content using semantic natural language query. Returns relevant code/text chunks.",
    parameters={
        "query": {
            "type": "string",
            "description": "The search query, e.g., 'where is the temporal engine initialized?'"
        }
    }
)
def semantic_file_search(query: str) -> str:
    if not chromadb:
        return "Error: chromadb is not installed. AxiomFS search is unavailable."
        
    db_dir = Path.home() / ".local" / "share" / "axiom" / "chromadb"
    if not db_dir.exists():
        return "Error: AxiomFS database not found."
        
    try:
        client = chromadb.PersistentClient(path=str(db_dir))
        try:
            collection = client.get_collection(name="axiom_fs")
        except Exception:
            return "Error: axiom_fs collection does not exist. Indexer may not be running."
            
        results = collection.query(
            query_texts=[query],
            n_results=3
        )
        
        if not results['documents'] or not results['documents'][0]:
            return "No matching files found."
            
        output = []
        for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
            file_path = meta.get("file_path", "Unknown File")
            output.append(f"--- File: {file_path} ---\n{doc}\n")
            
        return "\n".join(output)
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        return f"Error executing semantic search: {e}"
