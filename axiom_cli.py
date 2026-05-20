#!/usr/bin/env python3
"""AXIOM - AI Orchestration Framework entry point."""

import sys
import logging
from axiom.main import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nShutdown requested by user")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
