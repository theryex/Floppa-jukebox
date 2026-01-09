from __future__ import annotations

from typing import Dict, Any, List, Optional

import numpy as np

from .audio import decode_audio
from .beats import extract_beats
from .config import AnalysisConfig, load_calibration
from .features import compute_frame_features, summarize_segment_features
from .segmentation import compute_novelty, segment_from_novelty


def _apply_affine(values: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return values * a + b


def _apply_confidence_mapping(values: np.ndarray, mapping: Dict[str, Any]) -> np.ndarray:
    src = np.asarray(mapping.get("source", []), dtype=float)
    tgt = np.asarray(mapping.get("target", []), dtype=float)
    if src.size == 0 or tgt.size == 0:
        return values
    return np.interp(values, src, tgt)


def _apply_pitch_power(values: np.ndarray, power: float) -> np.ndarray:
    if power is None:
        return values
    return np.power(values, power)


def _segment_confidence(novelty: np.ndarray, frame_times: np.ndarray, start: float) -> float:
    if novelty.size == 0:
        return 0.5
    idx = np.searchsorted(frame_times, start, side="left")
    idx = min(max(idx, 0), len(novelty) - 1)
    min_n, max_n = float(novelty.min()), float(novelty.max())
    if max_n - min_n < 1e-6:
        return 0.5
    return float((novelty[idx] - min_n) / (max_n - min_n))


def _make_quanta(starts: List[float], duration: float, confidence: Optional[List[float]] = None) -> List[Dict[str, Any]]:
    quanta = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else duration
        q = {
            "start": float(start),
            "duration": float(max(0.0, end - start)),
        }
        if confidence:
            q["confidence"] = float(confidence[i])
        quanta.append(q)
    return quanta


def analyze_audio(audio_path: str, calibration_path: Optional[str] = None) -> Dict[str, Any]:
    config = AnalysisConfig()
    calibration = None
    if calibration_path:
        calibration = load_calibration(calibration_path)
        config_data = calibration.get("config")
        if config_data:
            config = AnalysisConfig.from_dict(config_data)

    audio, sample_rate = decode_audio(audio_path, sample_rate=config.features.sample_rate)
    duration = len(audio) / sample_rate if sample_rate else 0.0

    beat_times, beat_numbers = extract_beats(audio, sample_rate)
    if not beat_times:
        beat_times = [0.0]
        beat_numbers = [1]

    frame_features = compute_frame_features(audio, config.features)
    novelty = compute_novelty(
        frame_features["mfcc"],
        frame_features["hpcp"],
        frame_features["rms_db"],
    )

    boundaries = segment_from_novelty(
        frame_features["frame_times"],
        novelty,
        beat_times,
        config.segmentation,
        duration,
    )

    segments = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        seg_feat = summarize_segment_features(frame_features, start, end)
        mfcc = seg_feat["mfcc"]
        timbre = mfcc[1:13] if len(mfcc) >= 13 else np.pad(mfcc, (0, 12 - len(mfcc)))
        hpcp = seg_feat["hpcp"]
        if hpcp.size == 0:
            pitches = np.zeros(12, dtype=float)
        else:
            max_val = float(np.max(hpcp)) if np.max(hpcp) > 0 else 1.0
            pitches = hpcp / max_val
        rms_seq = np.asarray(seg_feat["rms_db"], dtype=float)
        loudness_start = float(rms_seq[0]) if rms_seq.size > 0 else 0.0
        loudness_max = float(rms_seq.max()) if rms_seq.size > 0 else 0.0
        if rms_seq.size > 0:
            max_idx = int(rms_seq.argmax())
            loudness_max_time = float(seg_feat["times"][max_idx] - start)
        else:
            loudness_max_time = 0.0
        confidence = _segment_confidence(novelty, frame_features["frame_times"], start)

        segment = {
            "start": float(start),
            "duration": float(max(0.0, end - start)),
            "confidence": float(confidence),
            "loudness_start": loudness_start,
            "loudness_max": loudness_max,
            "loudness_max_time": loudness_max_time,
            "pitches": pitches.tolist(),
            "timbre": timbre.astype(float).tolist(),
        }
        segments.append(segment)

    if calibration:
        timbre_map = calibration.get("timbre")
        loud_map = calibration.get("loudness")
        conf_map = calibration.get("confidence")
        pitch_map = calibration.get("pitch")
        for seg in segments:
            if timbre_map:
                a = np.asarray(timbre_map.get("a", [1.0] * 12))
                b = np.asarray(timbre_map.get("b", [0.0] * 12))
                seg["timbre"] = _apply_affine(np.asarray(seg["timbre"]), a, b).tolist()
            if loud_map:
                la = float(loud_map.get("a", 1.0))
                lb = float(loud_map.get("b", 0.0))
                seg["loudness_start"] = float(seg["loudness_start"] * la + lb)
                seg["loudness_max"] = float(seg["loudness_max"] * la + lb)
            if conf_map:
                seg["confidence"] = float(_apply_confidence_mapping(
                    np.asarray([seg["confidence"]]), conf_map
                )[0])
            if pitch_map and "power" in pitch_map:
                seg["pitches"] = _apply_pitch_power(
                    np.asarray(seg["pitches"]), float(pitch_map["power"])
                ).tolist()

    beats = _make_quanta(beat_times, duration, confidence=[1.0] * len(beat_times))

    # Bars based on downbeat indices (1-based within bar).
    bar_starts = [t for t, num in zip(beat_times, beat_numbers) if num == 1]
    if not bar_starts:
        bar_starts = [beat_times[0]]
    bars = _make_quanta(bar_starts, duration, confidence=[1.0] * len(bar_starts))

    # Tatums derived from beats.
    tatum_starts = []
    for i, beat in enumerate(beat_times):
        next_beat = beat_times[i + 1] if i + 1 < len(beat_times) else duration
        beat_duration = max(0.0, next_beat - beat)
        for t in range(config.tatums_per_beat):
            tatum_starts.append(beat + (beat_duration * t / config.tatums_per_beat))
    tatums = _make_quanta(sorted(set(tatum_starts)), duration, confidence=[1.0] * len(set(tatum_starts)))

    sections = _make_quanta([0.0], duration, confidence=[1.0])

    tempos = []
    for i in range(len(beat_times) - 1):
        dt = beat_times[i + 1] - beat_times[i]
        if dt > 0:
            tempos.append(60.0 / dt)
    tempo = float(np.median(tempos)) if tempos else 0.0

    analysis = {
        "sections": sections,
        "bars": bars,
        "beats": beats,
        "tatums": tatums,
        "segments": segments,
        "track": {
            "duration": float(duration),
            "tempo": float(tempo),
            "time_signature": float(config.time_signature),
        },
    }

    return analysis
