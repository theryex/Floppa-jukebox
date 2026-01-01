"""Audio analysis package."""

import os

os.environ.setdefault("NUMBA_DISABLE_JIT", "1")
os.environ.setdefault("NUMBA_DISABLE_CACHING", "1")

from .analyzer import analyze_audio

__all__ = ["analyze_audio"]
