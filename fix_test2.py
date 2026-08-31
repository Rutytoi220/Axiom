with open('tests/unit/test_telemetry_hardware.py', 'r') as f:
    content = f.read()

content = content.replace("try:\\\\n            await service._tick_loop()\\\\n        except asyncio.CancelledError:\\\\n            pass", 
"""try:
            await service._tick_loop()
        except asyncio.CancelledError:
            pass""")

with open('tests/unit/test_telemetry_hardware.py', 'w') as f:
    f.write(content)
