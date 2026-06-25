"""Compatibility shim: import generate from :mod:`core.llm`.

Kept for backward compatibility with code importing `ollama_handler.generate`.
"""

from core.llm import generate

__all__ = ["generate"]