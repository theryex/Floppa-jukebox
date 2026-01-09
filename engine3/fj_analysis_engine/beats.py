from typing import List, Tuple

import collections
import collections.abc
import warnings

import numpy as np


def extract_beats(audio: np.ndarray, sample_rate: int) -> Tuple[List[float], List[int]]:
    """Return beat times and beat numbers (1-based within bar)."""
    if not hasattr(collections, "MutableSequence"):
        collections.MutableSequence = collections.abc.MutableSequence
    if not hasattr(collections, "MutableMapping"):
        collections.MutableMapping = collections.abc.MutableMapping
    if not hasattr(collections, "MutableSet"):
        collections.MutableSet = collections.abc.MutableSet
    # Avoid NumPy deprecation warnings by checking the module dict directly.
    if "float" not in np.__dict__:
        np.float = float
    if "int" not in np.__dict__:
        np.int = int
    if "bool" not in np.__dict__:
        np.bool = bool
    if "complex" not in np.__dict__:
        np.complex = complex
    warnings.filterwarnings(
        "ignore",
        message="pkg_resources is deprecated as an API.*",
        category=UserWarning,
        module="madmom",
    )
    try:
        from madmom.audio.signal import Signal
        from madmom.features.downbeats import DBNDownBeatTrackingProcessor, RNNDownBeatProcessor
    except ImportError as exc:
        raise RuntimeError("madmom is required for beat/downbeat extraction") from exc

    signal = Signal(audio, sample_rate)
    proc = RNNDownBeatProcessor()
    act = proc(signal)
    tracker = DBNDownBeatTrackingProcessor(beats_per_bar=[3, 4], fps=100)
    try:
        downbeats = tracker(act)
        times = downbeats[:, 0].tolist()
        beat_numbers = downbeats[:, 1].astype(int).tolist()
        if times:
            return times, beat_numbers
    except Exception:
        pass

    try:
        from madmom.features.beats import DBNBeatTrackingProcessor, RNNBeatProcessor
    except ImportError as exc:
        raise RuntimeError("madmom is required for beat/downbeat extraction") from exc

    beat_act = RNNBeatProcessor()(signal)
    beat_tracker = DBNBeatTrackingProcessor(fps=100)
    beats = beat_tracker(beat_act)
    beats_arr = np.asarray(beats)
    if beats_arr.ndim == 1:
        times = beats_arr.tolist()
    else:
        times = beats_arr[:, 0].tolist()
    beat_numbers = [(i % 4) + 1 for i in range(len(times))]
    return times, beat_numbers
