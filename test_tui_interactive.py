"""Automated E2E pexpect test for AXIOM TUI interactive input handling."""
import pexpect
import sys
import time

def test_tui_interactive_flow():
    print(">>> Spawning AXIOM TUI via pexpect...")
    child = pexpect.spawn(
        "uv run python3 -m axiom.cli.tui",
        dimensions=(35, 120),
        encoding="utf-8",
        timeout=15,
    )
    
    # Enable logging to stdout
    child.logfile = sys.stdout

    try:
        # 1. Expect initial TUI render
        print("\n>>> Waiting for initial TUI interface...")
        child.expect(["AXIOM", "Session:", "❯"], timeout=10)
        time.sleep(1.0)

        # 2. Test slash command: /session
        print("\n>>> Testing /session command...")
        child.send("/session live_test_session\r")
        child.expect(r"Switched to session 'live_test_session'", timeout=5)
        print("\n>>> /session successfully switched without error!")

        # 3. Test user prompt input (triggering handle_accept with normal message)
        print("\n>>> Testing regular user prompt through handle_accept...")
        user_message = "Test ping from pexpect harness"
        child.send(f"{user_message}\r")
        
        # Verify the user text was processed and added to chat history
        child.expect(user_message, timeout=5)
        print(f"\n>>> Verified: user message '{user_message}' routed without UnboundLocalError!")

        # Verify Axiom response header was posted
        child.expect(["◈ Axiom:", "AXIOM is spinning up compute node"], timeout=5)
        print("\n>>> Verified: backend response initiation triggered successfully!")

        # Let the interface settle for 1 second
        time.sleep(1.0)

        # 4. Exit cleanly via Ctrl+C
        print("\n>>> Sending Ctrl+C to terminate TUI cleanly...")
        child.send("\x03")
        child.expect(pexpect.EOF, timeout=5)
        print("\n>>> TUI process terminated cleanly!")

    except Exception as e:
        print(f"\n[FAILURE] Exception during TUI interactive test: {e}")
        child.close(force=True)
        sys.exit(1)
    finally:
        if child.isalive():
            child.close(force=True)

    print("\n✅ All interactive TUI pexpect assertions passed!")

if __name__ == "__main__":
    test_tui_interactive_flow()
