with open('tests/unit/test_memory_compaction.py', 'r') as f:
    content = f.read()

content = content.replace('class MockStore:\n        db_path = "/tmp/mock.db"\n    def __init__(self, db_conn):', 'class MockStore:\n    db_path = "/tmp/mock.db"\n    def __init__(self, db_conn):')

with open('tests/unit/test_memory_compaction.py', 'w') as f:
    f.write(content)
