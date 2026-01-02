"""I/O helpers for analysis output."""

from __future__ import annotations

from typing import Any


def _round_floats(obj: Any, ndigits: int = 5) -> Any:
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, list):
        return [_round_floats(item, ndigits) for item in obj]
    if isinstance(obj, dict):
        return {key: _round_floats(value, ndigits) for key, value in obj.items()}
    return obj


def _sanitize_small_values(obj: Any, parent_key: str | None = None, threshold: float = 1e-4) -> Any:
    if isinstance(obj, float):
        if parent_key not in {"pitches", "timbre"} and abs(obj) < threshold:
            return 0.0
        return obj
    if isinstance(obj, list):
        return [_sanitize_small_values(item, parent_key, threshold) for item in obj]
    if isinstance(obj, dict):
        return {key: _sanitize_small_values(value, key, threshold) for key, value in obj.items()}
    return obj


def _read_track_metadata(path: str) -> dict[str, str]:
    try:
        from mutagen import File as MutagenFile
    except Exception:
        return {}

    try:
        audio = MutagenFile(path, easy=True)
    except Exception:
        return {}

    if not audio or not getattr(audio, "tags", None):
        return {}

    def first_tag_value(key: str) -> str | None:
        value = audio.tags.get(key)
        if not value:
            return None
        if isinstance(value, list):
            return str(value[0]) if value else None
        return str(value)

    metadata: dict[str, str] = {}
    title = first_tag_value("title")
    artist = first_tag_value("artist")
    if title:
        metadata["title"] = title
    if artist:
        metadata["artist"] = artist
    return metadata
