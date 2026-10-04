"""Comprehensive verification test for inline /model selector and Two-Brain VRAM eviction."""
import asyncio
import pexpect
import subprocess
import sys
import time
import httpx
import torch

from axiom.config import get_config
from axiom.agents.native_orchestrator import NativeOrchestrator
from axiom.core.vision_engine.singleton import get_grounding_engine, evict_grounding_engine
from axiom.core.vision_engine.axiom_engine import AxiomGroundingEngine


def test_1_interactive_model_picker():
    print("=" * 60)
    print("CHECK 1: Interactive Inline /model Selector")
    print("=" * 60)

    child = pexpect.spawn(
        "uv run python3 -m axiom.cli.repl",
        dimensions=(35, 120),
        encoding="utf-8",
        timeout=20,
    )
    child.logfile = sys.stdout

    try:
        child.expect(r"Local-First AI Orchestrator", timeout=10)
        child.expect(r"❯", timeout=5)

        # 1. Test /model with no args (triggers inline interactive picker)
        print("\n>>> Triggering /model interactive picker...")
        child.send("/model\r")
        child.expect(r"Select Model", timeout=8)
        time.sleep(0.5)

        # Press Enter to select current/first model
        child.send("\r")
        child.expect(r"✓ Switched model to:", timeout=8)
        print("\n✓ Interactive model picker selected model cleanly.")

        # 2. Test /model <name> direct switch
        print("\n>>> Testing direct switch /model qwen2.5-coder-custom:7b...")
        child.send("/model qwen2.5-coder-custom:7b\r")
        child.expect(r"✓ Switched model to: qwen2.5-coder-custom:7b", timeout=5)
        print("\n✓ Direct /model <name> switch verified.")

        # Clean exit
        child.sendline("/exit")
        child.expect(r"Goodbye.", timeout=5)
        child.expect(pexpect.EOF, timeout=5)
        print("\n✓ Check 1 PASSED: Interactive model selector works in both modes.")

    finally:
        if child.isalive():
            child.close(force=True)


async def test_2_ollama_num_gpu_offload():
    print("\n" + "=" * 60)
    print("CHECK 2: Ollama num_gpu=99 Full GPU Allocation")
    print("=" * 60)

    config = get_config()
    base_url = getattr(config, "ollama_base_url", "http://127.0.0.1:11434").rstrip("/")

    # Ensure vision model is evicted before querying Ollama
    evict_grounding_engine()

    orchestrator = NativeOrchestrator()
    payload = {
        "model": config.ollama_model,
        "messages": [{"role": "user", "content": "respond with 'pong'"}],
        "tools": [],
        "stream": True,
    }

    # Consume stream
    collected = ""
    async for chunk in orchestrator.generate_stream(payload):
        delta = chunk.get("choices", [{}])[0].get("delta", {})
        if "content" in delta:
            collected += delta["content"]

    print(f"\nModel output: {collected.strip()}")

    # Verify that payload options has num_gpu=99
    assert payload.get("options", {}).get("num_gpu") == 99, f"Expected num_gpu=99, got {payload.get('options')}"
    print("✓ Verified: payload['options']['num_gpu'] == 99.")

    # Check `ollama ps` to assert 100% GPU offload
    ps_proc = subprocess.run(["ollama", "ps"], capture_output=True, text=True)
    print(f"ollama ps output:\n{ps_proc.stdout}")
    assert "100% GPU" in ps_proc.stdout, f"Expected '100% GPU' in ollama ps, got:\n{ps_proc.stdout}"
    print("✓ Check 2 PASSED: Model is confirmed 100% offloaded to GPU.")


def test_3_vram_mutual_eviction():
    print("\n" + "=" * 60)
    print("CHECK 3: Strict Two-Brain VRAM Eviction (Vision <-> Text)")
    print("=" * 60)

    if not torch.cuda.is_available():
        print("CUDA not available, skipping CUDA memory allocation assertions.")
        return

    config = get_config()
    base_url = getattr(config, "ollama_base_url", "http://127.0.0.1:11434").rstrip("/")

    # 1. Evict Ollama to make room for vision engine
    print("Evicting Ollama text model...")
    with httpx.Client() as client:
        client.post(f"{base_url}/api/generate", json={"model": config.ollama_model, "keep_alive": 0})
    time.sleep(1.0)

    # 2. Boot Vision Engine
    print("Bootstrapping vision engine...")
    engine = get_grounding_engine()
    assert AxiomGroundingEngine._instance is not None
    vram_loaded = torch.cuda.memory_allocated()
    print(f"CUDA memory with vision engine: {vram_loaded / (1024**3):.2f} GB")
    assert vram_loaded > 1 * (1024**3), f"Expected > 1GB allocated, got {vram_loaded}"

    # 3. Evict Vision Engine
    print("Evicting vision engine...")
    evict_grounding_engine()
    assert AxiomGroundingEngine._instance is None
    vram_evicted = torch.cuda.memory_allocated()
    print(f"CUDA memory after vision engine eviction: {vram_evicted / (1024**2):.2f} MB")
    assert vram_evicted < vram_loaded, f"Expected memory to drop, was {vram_loaded} now {vram_evicted}"
    print("✓ Check 3 PASSED: Vision engine evicted cleanly, VRAM returned to free pool.")


async def main_suite():
    test_1_interactive_model_picker()
    await test_2_ollama_num_gpu_offload()
    test_3_vram_mutual_eviction()
    print("\n" + "=" * 60)
    print("✅ ALL MODEL PICKER AND VRAM OFFLOAD CHECKS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main_suite())
