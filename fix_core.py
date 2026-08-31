with open('tests/integration/test_core_systems_integration.py', 'r') as f:
    content = f.read()

bad_block = """    assert len(compressed) == 3
    # First older log metadata should be stripped
    assert "metadata" not in compressed[0].get("result", {})
    
    # Large older log should be severely truncated
    out_large = compressed[1]["result"]["output"]
    assert len(out_large) < 15000
    assert "semantically truncated" in out_large
    
    # Newest log untouched
    assert compressed[2]["result"]["output"] == "latest info\""""

good_block = """    assert len(compressed) == 2
    # First older logs should be aggregated into a SYSTEM hard-prune message
    assert compressed[0]["tool"] == "system"
    assert "hard-pruned" in compressed[0]["result"]["output"]
    assert "shell" in compressed[0]["result"]["output"]
    assert "file_read" in compressed[0]["result"]["output"]
    
    # Newest log untouched
    assert compressed[1]["result"]["output"] == "latest info\""""

content = content.replace(bad_block, good_block)

with open('tests/integration/test_core_systems_integration.py', 'w') as f:
    f.write(content)
