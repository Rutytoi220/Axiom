import os

print("Applying manual override to bridge.py...")
bridge_path = 'axiom/gui/bridge.py'

if os.path.exists(bridge_path):
    with open(bridge_path, 'r') as f:
        data = f.read()
    
    # Inject a 3-second sleep right after the subprocess fallback is triggered
    if 'import time' not in data:
        data = "import time\n" + data
        
    target_log = 'logger.info("Started daemon via subprocess fallback.")'
    if target_log in data and 'time.sleep(3)' not in data:
        data = data.replace(
            target_log,
            target_log + '\n        print("[GUI] Waiting 3 seconds for daemon to bind to port 9410...")\n        time.sleep(3)'
        )
        with open(bridge_path, 'w') as f:
            f.write(data)
        print("✅ Segfault connection loop patched!")
    else:
        print("⚠️ Subprocess log not found or already patched.")
else:
    print(f"❌ Could not find {bridge_path}")
