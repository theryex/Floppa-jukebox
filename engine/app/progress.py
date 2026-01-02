"""Progress reporting helpers."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

from .constants import PROGRESS_JOIN_TIMEOUT_S


@dataclass
class ProgressReporter:
    callback: Callable[[int, str], None] | None
    last_progress: int = -1

    def report(self, percent: int, stage: str) -> None:
        if not self.callback:
            return
        percent = max(self.last_progress, percent)
        if percent == self.last_progress and stage.startswith("beats_wait"):
            return
        self.last_progress = percent
        self.callback(percent, stage)

    def ramp(self, start_pct: int, end_pct: int, stage: str, duration: float) -> tuple[threading.Event, threading.Thread] | None:
        if not self.callback:
            return None
        stop_event = threading.Event()
        duration_s = max(20.0, min(120.0, duration * 0.6 if duration else 60.0))
        rate = (end_pct - start_pct) / duration_s if duration_s > 0 else 0.5

        def runner() -> None:
            start_time = time.time()
            while not stop_event.is_set():
                elapsed = time.time() - start_time
                pct = start_pct + int(elapsed * rate)
                pct = min(end_pct, max(start_pct, pct))
                self.report(pct, stage)
                if pct >= end_pct:
                    break
                stop_event.wait(0.5)

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        return stop_event, thread

    def stop_ramp(self, ramp: tuple[threading.Event, threading.Thread] | None) -> None:
        if not ramp:
            return
        stop_event, thread = ramp
        stop_event.set()
        thread.join(PROGRESS_JOIN_TIMEOUT_S)
