import re

with open('tests/test_orchestrator_fallback.py', 'r') as f:
    content = f.read()

# Replace all with orchestration
content = content.replace('mock_llm.config.model = "default"', 'mock_llm.config.model = "default"\n    mock_llm._classify_task = __import__("unittest.mock").mock.Mock()\n    mock_llm._classify_task.return_value = "orchestration"')

with open('tests/test_orchestrator_fallback.py', 'w') as f:
    f.write(content)

with open('tests/test_resilience.py', 'r') as f:
    content = f.read()

content = content.replace('agent.set_llm(llm)', 'agent.set_llm(llm)\n        llm._classify_task = __import__("unittest.mock").mock.Mock()\n        llm._classify_task.return_value = "orchestration"')

with open('tests/test_resilience.py', 'w') as f:
    f.write(content)

