# Contributing to AXIOM

First off, thank you for considering contributing to AXIOM! 

## Setting up your Development Environment

1. Fork the repository and clone your fork.
2. Ensure you have Python 3.12+ installed.
3. Install the dependencies and development tools:
   ```bash
   pip install -e ".[dev]"
   ```
4. Run the test suite to ensure everything is working:
   ```bash
   pytest tests/
   ```

## Development Workflow

- **Branch Naming:** Use descriptive branch names (e.g., `feature/add-docker-plugin`, `bugfix/sqlite-timeout`).
- **Code Style:** We use `black` for formatting and `flake8` for linting. Please ensure your code passes both before submitting a PR.
- **Testing:** All new features or bug fixes must include corresponding tests in the `tests/` directory. We aim for high coverage.

## Submitting a Pull Request

1. Push your changes to your fork.
2. Open a Pull Request against the `main` branch.
3. Clearly describe the problem you are solving and how your changes address it.
4. Ensure all CI checks pass.

## Architecture

Before making major changes, please read the `ARCHITECTURE.md` file in the root directory to understand the event bus, memory system, and tool registry patterns.

Thank you for helping make AXIOM better!
