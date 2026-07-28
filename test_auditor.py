import asyncio
from axiom.engine.cyber_auditor import SecurityAuditorAgent

async def main():
    agent = SecurityAuditorAgent(event_bus=None, tool_registry=None, llm_client=None)
    res = await agent.run_audit()
    print("Auditor Result:")
    import json
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
