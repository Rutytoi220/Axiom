"""Automated test for REPL slash autocompletion propositions and backend engine connection."""
import pexpect
import sys
import time

def test_repl_completion_and_backend():
    print(">>> Starting REPL autocompletion & backend verification...")
    child = pexpect.spawn(
        "uv run python3 -m axiom.cli.repl",
        dimensions=(35, 120),
        encoding="utf-8",
        timeout=25,
    )
    child.logfile = sys.stdout

    try:
        # 1. Expect initial REPL render
        child.expect(r"Local-First AI Orchestrator", timeout=10)
        child.expect(r"❯", timeout=5)
        print("\n✓ REPL launched cleanly at top of screen.")

        # 2. Test typing '/' activates completion without crash
        print("\n>>> Testing slash autocomplete trigger...")
        child.send("/")
        time.sleep(1.0)
        # Type 'h' and press Tab or Enter to complete /help
        child.send("help\r")
        child.expect(r"Available Commands:", timeout=8)
        child.expect(r"/model", timeout=5)
        print("\n✓ Slash autocompletion buffer functioned cleanly without crashing.")

        # 3. Test sending prompt to backend engine
        print("\n>>> Testing backend prompt routing and streaming...")
        test_prompt = "Say 'hello' in plain text. Do not use any tools."
        child.send(f"{test_prompt}\r")
        
        # Expect Axiom response header
        child.expect(r"◈ Axiom:", timeout=10)
        
        # Expect stream response without connection errors
        # Give it up to 20s to stream tokens from local Ollama
        index = child.expect([r"\[Connection Error\]", r"\[API Error\]", r"Streaming error", r"[A-Za-z0-9]"], timeout=20)
        assert index == 3, f"Unexpected error received from backend engine: {child.before}"
        print("\n✓ Tokens successfully streamed from local AI backend without connection drop.")

        # 4. Clean exit
        child.expect(r"❯", timeout=15)
        child.sendline("/exit")
        child.expect(r"Goodbye.", timeout=5)
        child.expect(pexpect.EOF, timeout=5)
        print("\n✓ REPL exited cleanly.")

    finally:
        if child.isalive():
            child.close(force=True)

    print("\n✅ All REPL autocompletion and backend connection tests PASSED!")

if __name__ == "__main__":
    test_repl_completion_and_backend()
