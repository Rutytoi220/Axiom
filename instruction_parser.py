"""Compatibility shim: import parser from :mod:`brain.parser`.

This file keeps the previous top-level import path `instruction_parser` working.
"""

from brain.parser import parse

__all__ = ["parse"]
