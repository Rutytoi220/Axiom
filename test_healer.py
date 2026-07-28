import asyncio
from axiom.engine.self_healer import HealerAgent

class MockLLM:
    def generate(self, messages, **kwargs):
        return {"content": "systemctl --user restart docker.service"}

agent = HealerAgent()
agent.llm_client = MockLLM()

res = agent.prescribe_and_execute("Service failure detected in docker.service", "docker.service", [])
print("HealerAgent result:", res)
