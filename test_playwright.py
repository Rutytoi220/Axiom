import asyncio
from axiom.tools.web_engine import PlaywrightWebTool

async def main():
    tool = PlaywrightWebTool()
    res = await tool("navigate", url="https://example.com")
    print("Navigate Result:", res)
    
    inspect = await tool("inspect")
    print("Inspect Result:", inspect["content"][:100] + "...")
    
    await tool.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
