import re

with open('axiom/llm/ollama_client.py', 'r') as f:
    code = f.read()

code = code.replace("async async def", "async def")

with open('axiom/llm/ollama_client.py', 'w') as f:
    f.write(code)
