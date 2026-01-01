"""Fit timbre calibration, merge into config, and run evaluation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from app.analyzer import analyze_audio
from app.config import config_from_dict
from scripts.fit_timbre_calibration import find_audio_for_stem
from scripts.evaluate import evaluate_pair


def normalized_similarity(summary: dict[str, Any]) -> dict[str, Any]:
    ranges = {
        "start": 60.0,
        "duration": 2.0,
        "confidence": 3.0,
        "loudness_start": 120.0,
        "loudness_max": 120.0,
        "loudness_max_time": 0.5,
        "pitches": 4.0,
        "timbre": 10000.0,
    }

    seg_fields = summary.get("segment_field_summary", {})
    pitch_mae = summary.get("pitches_error_summary", {}).get("mae", 0.0)
    timbre_mae = summary.get("timbre_error_summary", {}).get("mae", 0.0)

    parts = {}
    if seg_fields:
        for field, metric in seg_fields.items():
            mae = metric.get("mae", 0.0)
            scale = ranges.get(field, 1.0)
            parts[field] = max(0.0, 1.0 - (mae / scale))
    parts["pitches"] = max(0.0, 1.0 - (pitch_mae / ranges["pitches"]))
    parts["timbre"] = max(0.0, 1.0 - (timbre_mae / ranges["timbre"]))

    if not parts:
        return {"overall": 0.0}

    import numpy as np

    overall = float(np.mean(list(parts.values())))
    return {"overall": overall, "components": parts}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fit timbre calibration and evaluate in one pass.")
    parser.add_argument("--audio-dir", default="audio", help="Directory with audio files.")
    parser.add_argument("--json-dir", default="analysis", help="Directory with reference JSON files.")
    parser.add_argument("--config", default="tuned_config.json", help="Base analysis config JSON.")
    parser.add_argument("--output-config", default="tuned_config.json", help="Config to write with calibration.")
    parser.add_argument("--output-report", default="evaluation_report.json", help="Evaluation report path.")
    parser.add_argument("--max-pairs", type=int, default=0, help="Limit number of pairs (0 = all).")
    parser.add_argument("--ridge", type=float, default=1e-3, help="Ridge regularization strength.")
    return parser.parse_args()


def fit_calibration(pairs: list[tuple[Path, Path]], config: dict[str, Any], ridge: float) -> dict[str, Any]:
    xs: list[list[float]] = []
    ys: list[list[float]] = []
    cfg = config_from_dict(config)
    total = len(pairs)
    skipped = 0
    for idx, (audio_path, json_path) in enumerate(pairs, start=1):
        try:
            reference = json.loads(json_path.read_text(encoding="utf-8"))
            predicted = analyze_audio(str(audio_path), config=cfg)
        except Exception:
            skipped += 1
            print(f"calibration {idx}/{total} (skipped {skipped})", end="\r", flush=True)
            continue
        ref_segments = reference.get("segments", [])
        pred_segments = predicted.get("segments", [])
        count = min(len(ref_segments), len(pred_segments))
        for seg_idx in range(count):
            ref_vec = ref_segments[seg_idx].get("timbre", [])
            pred_vec = pred_segments[seg_idx].get("timbre", [])
            if len(ref_vec) != len(pred_vec) or not ref_vec:
                continue
            xs.append([float(v) for v in pred_vec])
            ys.append([float(v) for v in ref_vec])
        print(f"calibration {idx}/{total} (skipped {skipped})", end="\r", flush=True)
    if total:
        print()

    if not xs:
        raise SystemExit("No paired timbre vectors found.")

    import numpy as np

    x = np.array(xs, dtype=float)
    y = np.array(ys, dtype=float)
    ones = np.ones((x.shape[0], 1), dtype=float)
    x_aug = np.concatenate([x, ones], axis=1)
    # Ridge-regularized solve to reduce extreme coefficients.
    xtx = x_aug.T @ x_aug
    ridge_mat = ridge * np.eye(xtx.shape[0])
    coeffs = np.linalg.solve(xtx + ridge_mat, x_aug.T @ y)

    matrix = coeffs[:-1, :]
    bias = coeffs[-1, :]
    return {"matrix": matrix.tolist(), "bias": bias.tolist(), "count": int(x.shape[0])}


def _align_segments(
    ref: list[dict[str, Any]], pred: list[dict[str, Any]]
) -> list[tuple[int, int, float]]:
    if not ref or not pred:
        return []
    ious = []
    for i, r in enumerate(ref):
        r_interval = (float(r["start"]), float(r["start"] + r["duration"]))
        for j, p in enumerate(pred):
            p_interval = (float(p["start"]), float(p["start"] + p["duration"]))
            iou = max(0.0, min(r_interval[1], p_interval[1]) - max(r_interval[0], p_interval[0]))
            union = max(r_interval[1], p_interval[1]) - min(r_interval[0], p_interval[0])
            iou = iou / union if union > 0 else 0.0
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


def fit_segment_scalar_calibration(
    pairs: list[tuple[Path, Path]],
    config: dict[str, Any],
    fields: list[str],
    ridge: float,
) -> dict[str, dict[str, float]]:
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
        matches = _align_segments(ref_segments, pred_segments)
        for ref_idx, pred_idx, _ in matches:
            ref = ref_segments[ref_idx]
            pred = pred_segments[pred_idx]
            for field in fields:
                if field in ref and field in pred:
                    data[field].append((float(pred[field]), float(ref[field])))

    scales: dict[str, float] = {}
    biases: dict[str, float] = {}
    for field, pairs_data in data.items():
        if not pairs_data:
            continue
        x = np.array([p for p, _ in pairs_data], dtype=float)
        y = np.array([r for _, r in pairs_data], dtype=float)
        ones = np.ones_like(x)
        xtx = np.array([[np.dot(x, x), np.dot(x, ones)], [np.dot(ones, x), np.dot(ones, ones)]], dtype=float)
        xty = np.array([np.dot(x, y), np.dot(ones, y)], dtype=float)
        ridge_mat = ridge * np.eye(2)
        coeffs = np.linalg.solve(xtx + ridge_mat, xty)
        scales[field] = float(coeffs[0])
        biases[field] = float(coeffs[1])

    return {"scale": scales, "bias": biases}


def fit_pitch_calibration(
    pairs: list[tuple[Path, Path]],
    config: dict[str, Any],
    ridge: float,
) -> dict[str, list[float]]:
    cfg = config_from_dict(config)
    bins = 12
    data: list[list[tuple[float, float]]] = [[] for _ in range(bins)]
    for audio_path, json_path in pairs:
        try:
            reference = json.loads(json_path.read_text(encoding="utf-8"))
            predicted = analyze_audio(str(audio_path), config=cfg)
        except Exception:
            continue
        ref_segments = reference.get("segments", [])
        pred_segments = predicted.get("segments", [])
        matches = _align_segments(ref_segments, pred_segments)
        for ref_idx, pred_idx, _ in matches:
            ref = ref_segments[ref_idx].get("pitches", [])
            pred = pred_segments[pred_idx].get("pitches", [])
            if len(ref) != bins or len(pred) != bins:
                continue
            for idx in range(bins):
                data[idx].append((float(pred[idx]), float(ref[idx])))

    scales = []
    biases = []
    for idx in range(bins):
        pairs_data = data[idx]
        if not pairs_data:
            scales.append(1.0)
            biases.append(0.0)
            continue
        x = np.array([p for p, _ in pairs_data], dtype=float)
        y = np.array([r for _, r in pairs_data], dtype=float)
        ones = np.ones_like(x)
        xtx = np.array([[np.dot(x, x), np.dot(x, ones)], [np.dot(ones, x), np.dot(ones, ones)]], dtype=float)
        xty = np.array([np.dot(x, y), np.dot(ones, y)], dtype=float)
        ridge_mat = ridge * np.eye(2)
        coeffs = np.linalg.solve(xtx + ridge_mat, xty)
        scales.append(float(coeffs[0]))
        biases.append(float(coeffs[1]))

    return {"scale": scales, "bias": biases}


def evaluate(pairs: list[tuple[Path, Path]], config: dict[str, Any], workers: int) -> dict[str, Any]:
    cfg = config_from_dict(config)
    reports = []
    total = len(pairs)

    if total:
        from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

        def run_executor(executor_cls):
            tasks = []
            results = []
            with executor_cls(max_workers=workers) as executor:
                for audio_path, json_path in pairs:
                    tasks.append(executor.submit(_evaluate_pair_safe, audio_path, json_path, cfg))
                done = 0
                for future in as_completed(tasks):
                    results.append(future.result())
                    done += 1
                    print(f"evaluation {done}/{total}", end="\r", flush=True)
            print()
            return results

        try:
            reports = run_executor(ProcessPoolExecutor)
        except PermissionError:
            reports = run_executor(ThreadPoolExecutor)
    else:
        reports = []

    valid_reports = [r for r in reports if isinstance(r.get("numeric_mae"), (int, float))]
    if valid_reports:
        import numpy as np

        avg_mae = float(np.mean([r["numeric_mae"] for r in valid_reports]))
        avg_mse = float(np.mean([r["numeric_mse"] for r in valid_reports]))
        avg_iou = float(np.mean([r["segment_iou"] for r in valid_reports]))
    else:
        avg_mae = avg_mse = avg_iou = 0.0

    def avg_metric(values: list[float]) -> float:
        import numpy as np

        return float(np.mean(values)) if values else 0.0

    segment_field_summary = {}
    if valid_reports:
        fields = valid_reports[0].get("segment_field_errors", {}).keys()
        for field in fields:
            maes = [r["segment_field_errors"][field]["mae"] for r in valid_reports]
            mses = [r["segment_field_errors"][field]["mse"] for r in valid_reports]
            segment_field_summary[field] = {
                "mae": avg_metric(maes),
                "mse": avg_metric(mses),
            }

    pitches_summary = {
        "mae": avg_metric([r.get("pitches_error", {}).get("mae", 0.0) for r in valid_reports]),
        "mse": avg_metric([r.get("pitches_error", {}).get("mse", 0.0) for r in valid_reports]),
    }
    timbre_summary = {
        "mae": avg_metric([r.get("timbre_error", {}).get("mae", 0.0) for r in valid_reports]),
        "mse": avg_metric([r.get("timbre_error", {}).get("mse", 0.0) for r in valid_reports]),
    }

    output = {
        "count": len(reports),
        "success_count": len(valid_reports),
        "error_count": len(reports) - len(valid_reports),
        "average_numeric_mae": avg_mae,
        "average_numeric_mse": avg_mse,
        "average_segment_iou": avg_iou,
        "segment_field_summary": segment_field_summary,
        "pitches_error_summary": pitches_summary,
        "timbre_error_summary": timbre_summary,
        "pairs": reports,
    }
    output["normalized_similarity"] = normalized_similarity(output)
    return output


def _evaluate_pair_safe(audio_path: Path, json_path: Path, cfg: Any) -> dict[str, Any]:
    try:
        return evaluate_pair(audio_path, json_path, cfg)
    except Exception as exc:  # noqa: BLE001
        return {
            "audio": str(audio_path),
            "reference": str(json_path),
            "error": f"{type(exc).__name__}: {exc}",
            "schema_errors": ["analysis failed"],
            "numeric_mae": None,
            "numeric_mse": None,
            "segment_iou": None,
        }


def main() -> None:
    args = parse_args()
    audio_dir = Path(args.audio_dir)
    json_dir = Path(args.json_dir)
    config_path = Path(args.config)

    config = json.loads(config_path.read_text(encoding="utf-8"))

    pairs: list[tuple[Path, Path]] = []
    for json_path in sorted(json_dir.glob("*.json")):
        audio_path = find_audio_for_stem(audio_dir, json_path.stem)
        if audio_path:
            pairs.append((audio_path, json_path))
        if args.max_pairs and len(pairs) >= args.max_pairs:
            break

    calibration = fit_calibration(pairs, config, args.ridge)
    config["timbre_calibration_matrix"] = calibration["matrix"]
    config["timbre_calibration_bias"] = calibration["bias"]

    scalar_fields = ["confidence", "loudness_start", "loudness_max", "loudness_max_time"]
    scalar_cal = fit_segment_scalar_calibration(pairs, config, scalar_fields, args.ridge)
    config["segment_scalar_scale"] = scalar_cal["scale"]
    config["segment_scalar_bias"] = scalar_cal["bias"]

    pitch_cal = fit_pitch_calibration(pairs, config, args.ridge)
    config["pitch_scale"] = pitch_cal["scale"]
    config["pitch_bias"] = pitch_cal["bias"]
    config["pitch_calibration_matrix"] = None
    config["pitch_calibration_bias"] = None
    config["segment_quantile_maps"] = None
    Path(args.output_config).write_text(json.dumps(config, indent=2), encoding="utf-8")

    eval_pairs = pairs[:20]
    report = evaluate(eval_pairs, config, workers=max(1, os.cpu_count() or 4))
    report["evaluation_pairs"] = len(eval_pairs)
    report["timbre_calibration"] = calibration
    report["segment_scalar_calibration"] = scalar_cal
    report["pitch_calibration"] = pitch_cal
    Path(args.output_report).write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
