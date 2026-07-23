from axiom.engine.tool_pruner import ToolPruner

def test_prune_schemas_chat_intent():
    raw_schemas = [{"name": "read_document_content"}, {"name": "execute_command"}]
    # Should return empty list for chat intent
    result = ToolPruner.prune_schemas("hello", raw_schemas, "chat")
    assert result == []

def test_prune_schemas_filesystem_cluster():
    raw_schemas = [
        {"name": "read_document_content"}, 
        {"name": "execute_command"},
        {"name": "capture_screenshot"}
    ]
    # "read" keyword triggers filesystem cluster
    result = ToolPruner.prune_schemas("I need to read a file", raw_schemas, "orchestration")
    assert len(result) == 1
    assert result[0]["name"] == "read_document_content"

def test_prune_schemas_fallback():
    raw_schemas = [
        {"name": "read_document_content"}, 
        {"name": "execute_command"}
    ]
    # No keywords match -> return all
    result = ToolPruner.prune_schemas("do something completely random", raw_schemas, "orchestration")
    assert len(result) == 2
