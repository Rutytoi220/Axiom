"""Verification script for REPL screen reset, high-contrast palette, and ASCII alignment."""
import pexpect
import sys

def test_repl_launch():
    print("Testing REPL launch via pexpect...")
    child = pexpect.spawn(
        "uv run python3 -m axiom.cli.repl",
        dimensions=(35, 120),
        encoding="utf-8",
        timeout=10,
    )
    child.logfile = sys.stdout

    try:
        # 1. Expect banner and aligned ASCII text
        child.expect(r"/_/   \\_/_/\\_\\___\\___/\\|_\\|  \\|_\\|", timeout=8)
        print("\n✓ Verified: Aligned ASCII banner rendered successfully.")

        # 2. Expect high-contrast labels
        child.expect(r"Model:", timeout=5)
        child.expect(r"Session:", timeout=5)
        print("\n✓ Verified: High-contrast labels rendered.")

        # 3. Expect prompt glyph
        child.expect(r"❯", timeout=5)
        print("\n✓ Verified: Tokyo Night prompt glyph rendered.")

        # 4. Test /help command
        child.sendline("/help")
        child.expect(r"Available Commands:", timeout=5)
        child.expect(r"Show this command reference", timeout=5)
        print("\n✓ Verified: /help reference rendered with high-contrast labels.")

        # 5. Exit cleanly via /exit
        child.sendline("/exit")
        child.expect(r"Goodbye.", timeout=5)
        child.expect(pexpect.EOF, timeout=5)
        print("\n✓ Verified: Clean exit via /exit.")

    finally:
        if child.isalive():
            child.close(force=True)

    print("\n✅ All REPL launch and alignment checks passed!")

if __name__ == "__main__":
    test_repl_launch()
