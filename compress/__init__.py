"""Compress subsystem for HeadMaster.

This package provides tools to compress natural language markdown files
to save input tokens. Preserves code blocks, URLs, headings, structure.
Overwrites original, saves backup as .original.md.
"""

__all__ = ["cli", "compress", "detect", "validate"]

__version__ = "2.0.0"
