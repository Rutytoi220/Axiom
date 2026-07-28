import asyncio
from axiom.services.ebpf_governor import VRAMGovernorService

async def main():
    class MockEventBus:
        async def publish_async(self, topic, data):
            print(f"MockEventBus published: {topic} -> {data}")
            
    gov = VRAMGovernorService(MockEventBus())
    await gov.start()
    
    # Simulate high latency
    print("Testing latency simulation...")
    async def hog():
        for i in range(3):
            # This synchronous sleep blocks the event loop, simulating a 50ms UI freeze
            import time
            time.sleep(0.05)
            await asyncio.sleep(0.1)
            
    await hog()
    await asyncio.sleep(2.5) # Wait for governor loop to tick
    gov.stop()

if __name__ == "__main__":
    asyncio.run(main())
