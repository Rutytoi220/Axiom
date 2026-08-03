import sys
import logging
from axiom.engine.router import SmartRouter
from axiom.llm.universal_client import UniversalLLMClient

# Setup basic logging to see SmartRouter's info messages
logging.basicConfig(level=logging.INFO, format="%(message)s")

def main():
    print("=== Testing AXIOM SmartRouter ===\n")
    
    # We create a dummy LLM client to pass to the router
    dummy_client = UniversalLLMClient()
    router = SmartRouter(llm_client=dummy_client)
    
    # Define a few test prompts with different complexities
    test_cases = [
        {
            "name": "General Chat",
            "messages": [{"role": "user", "content": "Hello! How are you doing today?"}]
        },
        {
            "name": "System Command",
            "messages": [{"role": "user", "content": "Please check the current CPU temperature and find the largest files in my Downloads folder."}]
        },
        {
            "name": "Coding/Refactoring",
            "messages": [{"role": "user", "content": "Can you rewrite this Python script to use asyncio and aiohttp instead of the synchronous requests library?"}]
        },
        {
            "name": "Deep Reasoning",
            "messages": [{"role": "user", "content": "Solve this logic puzzle: If A is heavier than B, and C is lighter than B, but D is exactly half the weight of A plus C. What is the order of weight from heaviest to lightest?"}]
        },
        {
            "name": "Cloud Burst Request",
            "messages": [{"role": "user", "content": "/cloud Can you write a really complicated novel about a space detective?"}]
        }
    ]
    
    for case in test_cases:
        print(f"\n--- Testing: {case['name']} ---")
        print(f"Prompt: {case['messages'][0]['content']}")
        try:
            target_model = router._route_request(case['messages'])
            print(f"Selected Model: {target_model}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
