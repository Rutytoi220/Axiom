import tomli
import tomli_w

with open("pyproject.toml", "rb") as f:
    data = tomli.load(f)

# Update core dependencies
core_deps = [
    "PySide6>=6.0",
    "litellm>=1.93.0",
    "websockets>=10.0",
    "Pillow>=9.0.0",
    "pydantic>=2.0",
    "chromadb>=0.4.0",
    "aiosqlite>=0.20.0",
    "fastapi>=0.100.0",
    "uvicorn>=0.20.0",
    "psutil>=5.9.0",
    "watchdog>=3.0.0",
    "structlog>=24.0.0",
]
data["project"]["dependencies"] = core_deps

# Add optional dependencies
if "optional-dependencies" not in data["project"]:
    data["project"]["optional-dependencies"] = {}

data["project"]["optional-dependencies"]["audio"] = [
    "faster-whisper>=1.0.0",
    "pyttsx3>=2.90",
    "openwakeword>=0.4.0",
    "sounddevice>=0.4.0",
    "piper-tts>=1.2.0"
]

data["project"]["optional-dependencies"]["automation"] = [
    "pyautogui>=0.9.54",
    "nxbt>=0.1.4"
]

data["project"]["optional-dependencies"]["experimental"] = [
    "networkx>=3.0",
    "wasmtime>=12.0.0",
    "textual>=0.30.0",
    "prompt_toolkit>=3.0.0",
    "fusepy>=3.0.1"
]

# Update dev dependencies (in dependency-groups)
if "dependency-groups" in data and "dev" in data["dependency-groups"]:
    dev_deps = data["dependency-groups"]["dev"]
    new_dev = ["pytest-cov>=4.0", "mypy>=1.0", "build>=1.0", "twine>=4.0", "pyinstaller>=6.0"]
    for dep in new_dev:
        # Just simple check
        dep_name = dep.split(">=")[0]
        if not any(d.startswith(dep_name) for d in dev_deps):
            dev_deps.append(dep)

with open("pyproject.toml", "wb") as f:
    tomli_w.dump(data, f)
