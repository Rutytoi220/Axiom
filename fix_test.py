with open('tests/unit/test_telemetry_hardware.py', 'r') as f:
    content = f.read()
    
# We just need to catch the CancelledError explicitly in the test
content = content.replace("await service._tick_loop()", "try:\\n            await service._tick_loop()\\n        except asyncio.CancelledError:\\n            pass")

with open('tests/unit/test_telemetry_hardware.py', 'w') as f:
    f.write(content)
