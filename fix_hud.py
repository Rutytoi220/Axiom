with open('tests/gui/test_telemetry_hud.py', 'r') as f:
    content = f.read()

content = content.replace('"vram_mb": 2048.0,\\n        "gpu_name": "Nvidia Discrete",', '"vram_mb": 2048.0,\n        "gpu_name": "Nvidia Discrete",')

with open('tests/gui/test_telemetry_hud.py', 'w') as f:
    f.write(content)
