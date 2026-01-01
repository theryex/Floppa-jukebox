"""Train calibration models on Spotify pairs and evaluate on a hold-out split."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import numpy as np

from app import features
from app.analyzer import analyze_audio
from app.config import config_from_dict
from scripts.calibrate_timbre_and_eval import evaluate, fit_calibration, fit_segment_scalar_calibration
from scripts.fit_timbre_calibration import find_audio_for_stem


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train calibration models using Spotify pairs.")
    parser.add_argument("--audio-dir", default="audio", help="Directory with audio files.")
    parser.add_argument("--json-dir", default="analysis_spotify", help="Directory with reference JSON files.")
    parser.add_argument("--config", default="tuned_config.json", help="Base analysis config JSON.")
    parser.add_argument("--output-config", default="tuned_config.json", help="Config to write with calibration.")
    parser.add_argument("--output-report", default="training_report.json", help="Training report path.")
    parser.add_argument("--split-file", default="training_split.json", help="Where to write split metadata.")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Validation ratio.")
    parser.add_argument("--seed", type=int, default=7, help="Shuffle seed.")
    parser.add_argument("--max-pairs", type=int, default=0, help="Limit total pairs (0 = all).")
    parser.add_argument("--ridge", type=float, default=1e-3, help="Ridge regularization strength.")
    parser.add_argument("--max-frames", type=int, default=500000, help="Max frames for PCA fit.")
    parser.add_argument("--boundary-only", action="store_true", help="Only retrain boundary model.")
    return parser.parse_args()


def collect_pairs(audio_dir: Path, json_dir: Path, max_pairs: int) -> list[tuple[Path, Path]]:
    pairs = []
    for json_path in sorted(json_dir.glob("*.json")):
        audio_path = find_audio_for_stem(audio_dir, json_path.stem)
        if audio_path:
            pairs.append((audio_path, json_path))
        if max_pairs and len(pairs) >= max_pairs:
            break
    return pairs


def align_segments(
    ref: list[dict[str, Any]], pred: list[dict[str, Any]]
) -> list[tuple[int, int, float]]:
    if not ref or not pred:
        return []
    ious = []
    for i, r in enumerate(ref):
        r_interval = (float(r["start"]), float(r["start"] + r["duration"]))
        for j, p in enumerate(pred):
            p_interval = (float(p["start"]), float(p["start"] + p["duration"]))
            inter = max(0.0, min(r_interval[1], p_interval[1]) - max(r_interval[0], p_interval[0]))
            union = max(r_interval[1], p_interval[1]) - min(r_interval[0], p_interval[0])
            iou = inter / union if union > 0 else 0.0
            ious.append((i, j, iou))
    ious.sort(key=lambda item: item[2], reverse=True)
    matched_ref = set()
    matched_pred = set()
    matches = []
    for i, j, iou in ious:
        if i in matched_ref or j in matched_pred:
            continue
        matched_ref.add(i)
        matched_pred.add(j)
        matches.append((i, j, iou))
        if len(matched_ref) == len(ref) or len(matched_pred) == len(pred):
            break
    return matches


def fit_timbre_pca(
    pairs: list[tuple[Path, Path]],
    config: dict[str, Any],
    max_frames: int,
) -> dict[str, Any]:
    cfg = config_from_dict(config)
    frame_length = max(256, int(round(cfg.sample_rate * cfg.mfcc_window_ms / 1000.0)))
    hop_length = max(1, int(round(cfg.sample_rate * cfg.mfcc_hop_ms / 1000.0)))

    frames = []
    total = 0
    for audio_path, _ in pairs:
        try:
            y, sr = features.load_audio(str(audio_path), sr=cfg.sample_rate)
        except Exception:
            continue
        log_mel = features.log_mel_frames(
            y,
            sr,
            hop_length=hop_length,
            frame_length=frame_length,
            n_mels=cfg.mfcc_n_mels,
        )
        if log_mel.size:
            frames.append(log_mel.T)
            total += log_mel.shape[1]
        if total >= max_frames:
            break

    if not frames:
        raise SystemExit("No audio frames loaded for PCA.")

    data = np.concatenate(frames, axis=0)
    if data.shape[0] > max_frames:
        step = max(1, data.shape[0] // max_frames)
        data = data[::step]

    mean = np.mean(data, axis=0)
    centered = data - mean
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    components = vt[: cfg.mfcc_n_mfcc]

    return {"mean": mean.tolist(), "components": components.tolist(), "count": int(data.shape[0])}


def fit_boundary_model(
    pairs: list[tuple[Path, Path]],
    config: dict[str, Any],
    ridge: float,
    max_frames: int,
) -> dict[str, Any]:
    cfg = config_from_dict(config)
    xs = []
    ys = []
    frame_length = features.DEFAULT_FRAME_LENGTH
    hop_length = cfg.hop_length
    feature_names = ["onset", "novelty", "beat"]

    for audio_path, json_path in pairs:
        try:
            reference = json.loads(json_path.read_text(encoding="utf-8"))
            y, sr = features.load_audio(str(audio_path), sr=cfg.sample_rate)
        except Exception:
            continue

        onset_env = features.onset_envelope(y, sr, hop_length=hop_length)
        mfcc_seg = features.mfcc_frames(
            y,
            sr,
            hop_length=hop_length,
            frame_length=frame_length,
            n_mfcc=cfg.mfcc_n_mfcc,
            n_mels=cfg.mfcc_n_mels,
            include_0th=cfg.mfcc_use_0th,
        )

        novelty = np.zeros(mfcc_seg.shape[1])
        for i in range(1, mfcc_seg.shape[1]):
            prev = mfcc_seg[:, i - 1]
            curr = mfcc_seg[:, i]
            denom = (np.linalg.norm(prev) * np.linalg.norm(curr)) + 1e-9
            novelty[i] = 1.0 - float(np.dot(prev, curr) / denom)

        min_len = min(len(novelty), len(onset_env))
        if min_len == 0:
            continue

        onset_norm = onset_env[:min_len]
        novelty_norm = novelty[:min_len]
        onset_norm = onset_norm / (np.max(onset_norm) + 1e-9)
        novelty_norm = novelty_norm / (np.max(novelty_norm) + 1e-9)

        tempo, beat_times, _ = features.beat_track(
            y,
            sr,
            hop_length=hop_length,
            min_bpm=cfg.tempo_min_bpm,
            max_bpm=cfg.tempo_max_bpm,
        )
        if beat_times.size == 0:
            duration = float(len(y) / sr) if sr else 0.0
            beat_times = np.arange(0.0, max(duration, 0.01), 60.0 / max(tempo, 1.0))

        beat_feat = np.zeros(min_len, dtype=float)
        beat_frames = features.time_to_frames(beat_times, sr, hop_length=hop_length)
        beat_frames = np.clip(beat_frames, 0, max(min_len - 1, 0))
        beat_frames = np.unique(beat_frames)
        for idx in range(len(beat_frames) - 1):
            start = int(beat_frames[idx])
            end = int(beat_frames[idx + 1])
            if end <= start:
                continue
            beat_feat[start:end] = float(np.mean(onset_norm[start:end])) if onset_norm.size else 0.0

        feature_map = {
            "onset": onset_norm,
            "novelty": novelty_norm,
            "beat": beat_feat,
        }
        features_mat = np.stack([feature_map[name] for name in feature_names], axis=1)

        labels = np.zeros(min_len, dtype=float)
        for seg in reference.get("segments", []):
            start = float(seg.get("start", 0.0))
            frame_idx = int(round(start * sr / hop_length))
            if 0 <= frame_idx < min_len:
                labels[frame_idx] = 1.0

        xs.append(features_mat)
        ys.append(labels)
        if sum(len(x) for x in xs) >= max_frames:
            break

    if not xs:
        return {"weights": [1.0, 1.0, 1.0], "bias": 0.0}

    x = np.concatenate(xs, axis=0)
    y = np.concatenate(ys, axis=0)
    if x.shape[0] > max_frames:
        step = max(1, x.shape[0] // max_frames)
        x = x[::step]
        y = y[::step]

    ones = np.ones((x.shape[0], 1), dtype=float)
    x_aug = np.concatenate([x, ones], axis=1)
    xtx = x_aug.T @ x_aug
    ridge_mat = ridge * np.eye(xtx.shape[0])
    coeffs = np.linalg.solve(xtx + ridge_mat, x_aug.T @ y)

    weights = coeffs[:-1].flatten()
    bias = float(coeffs[-1])
    return {"weights": weights.tolist(), "bias": bias}


def fit_pitch_matrix(
    pairs: list[tuple[Path, Path]],
    config: dict[str, Any],
    ridge: float,
) -> dict[str, Any]:
    cfg = config_from_dict(config)
    bins = 12
    xs: list[list[float]] = []
    ys: list[list[float]] = []
    for audio_path, json_path in pairs:
        try:
            reference = json.loads(json_path.read_text(encoding="utf-8"))
            predicted = analyze_audio(str(audio_path), config=cfg)
        except Exception:
            continue
        ref_segments = reference.get("segments", [])
        pred_segments = predicted.get("segments", [])
        matches = align_segments(ref_segments, pred_segments)
        for ref_idx, pred_idx, _ in matches:
            ref = ref_segments[ref_idx].get("pitches", [])
            pred = pred_segments[pred_idx].get("pitches", [])
            if len(ref) != bins or len(pred) != bins:
                continue
            xs.append([float(v) for v in pred])
            ys.append([float(v) for v in ref])

    if not xs:
        return {"matrix": np.eye(bins).tolist(), "bias": np.zeros(bins).tolist()}

    x = np.array(xs, dtype=float)
    y = np.array(ys, dtype=float)
    ones = np.ones((x.shape[0], 1), dtype=float)
    x_aug = np.concatenate([x, ones], axis=1)
    xtx = x_aug.T @ x_aug
    ridge_mat = ridge * np.eye(xtx.shape[0])
    coeffs = np.linalg.solve(xtx + ridge_mat, x_aug.T @ y)

    matrix = coeffs[:-1, :]
    bias = coeffs[-1, :]
    return {"matrix": matrix.tolist(), "bias": bias.tolist()}


def fit_quantile_maps(
    pairs: list[tuple[Path, Path]],
    config: dict[str, Any],
    fields: list[str],
    quantiles: int = 101,
) -> dict[str, dict[str, list[float]]]:
    cfg = config_from_dict(config)
    data: dict[str, list[tuple[float, float]]] = {field: [] for field in fields}
    for audio_path, json_path in pairs:
        try:
            reference = json.loads(json_path.read_text(encoding="utf-8"))
            predicted = analyze_audio(str(audio_path), config=cfg)
        except Exception:
            continue
        ref_segments = reference.get("segments", [])
        pred_segments = predicted.get("segments", [])
        matches = align_segments(ref_segments, pred_segments)
        for ref_idx, pred_idx, _ in matches:
            ref = ref_segments[ref_idx]
            pred = pred_segments[pred_idx]
            for field in fields:
                if field in ref and field in pred:
                    data[field].append((float(pred[field]), float(ref[field])))

    maps: dict[str, dict[str, list[float]]] = {}
    probs = np.linspace(0.0, 1.0, quantiles)
    for field, pairs_data in data.items():
        if not pairs_data:
            continue
        pred_vals = np.array([p for p, _ in pairs_data], dtype=float)
        ref_vals = np.array([r for _, r in pairs_data], dtype=float)
        src = np.quantile(pred_vals, probs).tolist()
        dst = np.quantile(ref_vals, probs).tolist()
        maps[field] = {"src": src, "dst": dst}

    return maps


def fit_start_offset_map(
    pairs: list[tuple[Path, Path]],
    config: dict[str, Any],
    bins: int = 51,
) -> dict[str, list[float]]:
    cfg = config_from_dict(config)
    norms = []
    offsets = []
    for audio_path, json_path in pairs:
        try:
            reference = json.loads(json_path.read_text(encoding="utf-8"))
            predicted = analyze_audio(str(audio_path), config=cfg)
        except Exception:
            continue
        ref_segments = reference.get("segments", [])
        pred_segments = predicted.get("segments", [])
        matches = align_segments(ref_segments, pred_segments)
        duration = float(reference.get("track", {}).get("duration", 0.0))
        if duration <= 0:
            continue
        for ref_idx, pred_idx, _ in matches:
            ref = ref_segments[ref_idx]
            pred = pred_segments[pred_idx]
            ref_start = float(ref.get("start", 0.0))
            pred_start = float(pred.get("start", 0.0))
            norms.append(pred_start / duration)
            offsets.append(ref_start - pred_start)

    if not norms:
        return {"src": [0.0, 1.0], "dst": [0.0, 0.0]}

    norms = np.array(norms, dtype=float)
    offsets = np.array(offsets, dtype=float)
    probs = np.linspace(0.0, 1.0, bins)
    src = np.quantile(norms, probs)
    dst = []
    for idx in range(len(src)):
        if idx == len(src) - 1:
            mask = norms >= src[idx]
        else:
            mask = (norms >= src[idx]) & (norms < src[idx + 1])
        if mask.any():
            dst.append(float(np.mean(offsets[mask])))
        else:
            dst.append(0.0)
    return {"src": src.tolist(), "dst": dst}


def main() -> None:
    args = parse_args()
    audio_dir = Path(args.audio_dir)
    json_dir = Path(args.json_dir)

    pairs = collect_pairs(audio_dir, json_dir, args.max_pairs)
    if not pairs:
        raise SystemExit("No audio/json pairs found.")

    random.seed(args.seed)
    random.shuffle(pairs)
    split_idx = max(1, int(len(pairs) * (1.0 - args.val_ratio)))
    train_pairs = pairs[:split_idx]
    val_pairs = pairs[split_idx:]

    split = {
        "seed": args.seed,
        "val_ratio": args.val_ratio,
        "train_count": len(train_pairs),
        "val_count": len(val_pairs),
        "train": [p[1].stem for p in train_pairs],
        "val": [p[1].stem for p in val_pairs],
    }
    Path(args.split_file).write_text(json.dumps(split, indent=2), encoding="utf-8")

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.boundary_only:
        boundary = fit_boundary_model(train_pairs, config, args.ridge, args.max_frames)
        config["boundary_model_weights"] = boundary["weights"]
        config["boundary_model_bias"] = boundary["bias"]
        Path(args.output_config).write_text(json.dumps(config, indent=2), encoding="utf-8")

        report = {"split": split, "boundary_only": True, "boundary_model": boundary}
        report["validation"] = evaluate(val_pairs, config, workers=max(1, os.cpu_count() or 4))
        Path(args.output_report).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return
    config["timbre_mode"] = "pca"
    config["timbre_unit_norm"] = True
    config["timbre_standardize"] = False
    config["timbre_scale"] = 1.0

    pca = fit_timbre_pca(train_pairs, config, args.max_frames)
    config["timbre_pca_components"] = pca["components"]
    config["timbre_pca_mean"] = pca["mean"]

    config["timbre_calibration_matrix"] = None
    config["timbre_calibration_bias"] = None
    timbre_cal = fit_calibration(train_pairs, config, args.ridge)
    config["timbre_calibration_matrix"] = timbre_cal["matrix"]
    config["timbre_calibration_bias"] = timbre_cal["bias"]

    scalar_fields = ["confidence", "loudness_start", "loudness_max", "loudness_max_time"]
    scalar_cal = fit_segment_scalar_calibration(train_pairs, config, scalar_fields, args.ridge)
    config["segment_scalar_scale"] = scalar_cal["scale"]
    config["segment_scalar_bias"] = scalar_cal["bias"]

    pitch_cal = fit_pitch_matrix(train_pairs, config, args.ridge)
    config["pitch_calibration_matrix"] = pitch_cal["matrix"]
    config["pitch_calibration_bias"] = pitch_cal["bias"]
    config["pitch_scale"] = None
    config["pitch_bias"] = None

    quantile_maps = fit_quantile_maps(
        train_pairs,
        config,
        fields=["confidence", "loudness_start", "loudness_max"],
    )
    config["segment_quantile_maps"] = quantile_maps

    # Compute target segment rate from training references.
    durations = []
    segment_counts = []
    section_counts = []
    for _, json_path in train_pairs:
        try:
            ref = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        duration = float(ref.get("track", {}).get("duration", 0.0))
        if duration <= 0:
            continue
        count = len(ref.get("segments", []))
        if count <= 0:
            continue
        durations.append(duration)
        segment_counts.append(count)
        section_counts.append(len(ref.get("sections", [])))
    if durations:
        total_duration = float(np.sum(durations))
        total_segments = float(np.sum(segment_counts))
        if total_duration > 0:
            config["target_segment_rate"] = total_segments / total_duration
            config["target_segment_rate_tolerance"] = 0.2
            total_sections = float(np.sum(section_counts))
            config["target_section_rate"] = total_sections / total_duration
            config["target_section_rate_tolerance"] = 0.2

    boundary = fit_boundary_model(train_pairs, config, args.ridge, args.max_frames)
    config["boundary_model_weights"] = boundary["weights"]
    config["boundary_model_bias"] = boundary["bias"]

    config["start_offset_map_src"] = None
    config["start_offset_map_dst"] = None

    Path(args.output_config).write_text(json.dumps(config, indent=2), encoding="utf-8")

    report = {
        "split": split,
        "pca": pca,
        "timbre_calibration": timbre_cal,
        "segment_scalar_calibration": scalar_cal,
        "pitch_calibration": pitch_cal,
        "segment_quantile_maps": quantile_maps,
        "boundary_model": boundary,
    }
    report["validation"] = evaluate(val_pairs, config, workers=max(1, os.cpu_count() or 4))
    Path(args.output_report).write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import os

    main()
