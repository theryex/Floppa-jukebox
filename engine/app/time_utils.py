"""Time and frame conversion helpers."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def frame_slice(time_start: float, time_end: float, sr: int, hop_length: int) -> tuple[int, int]:
    start = int(math.floor(time_start * sr / hop_length))
    end = int(math.ceil(time_end * sr / hop_length))
    return max(0, start), max(start + 1, end)


def time_to_frames(times: Iterable[float], sr: int, hop_length: int) -> np.ndarray:
    times = np.array(list(times), dtype=float)
    return np.round(times * sr / hop_length).astype(int)


def frames_to_time(frames: Iterable[int], sr: int, hop_length: int) -> np.ndarray:
    frames = np.array(list(frames), dtype=float)
    return frames * hop_length / sr
