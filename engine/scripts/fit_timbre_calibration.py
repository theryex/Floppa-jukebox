"""Fit an affine calibration for timbre vectors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from app.analyzer import analyze_audio
from app.config import config_from_dict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fit timbre calibration from paired audio/JSON.")
    parser.add_argument("--audio-dir", default="audio", help="Directory with audio files.")
    parser.add_argument("--json-dir", default="analysis", help="Directory with reference JSON files.")
    parser.add_argument("--config", help="Path to analysis config JSON.")
    parser.add_argument("--output", default="timbre_calibration.json", help="Output calibration JSON.")
    parser.add_argument("--max-pairs", type=int, default=0, help="Limit number of pairs (0 = all).")
    return parser.parse_args()


def find_audio_for_stem(audio_dir: Path, stem: str) -> Path | None:
    candidate = audio_dir / stem
    if candidate.exists() and candidate.is_file():
        return candidate
    for ext in (".wav", ".mp3", ".m4a", ".flac", ".ogg"):
        candidate = audio_dir / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def main() -> None:
    args = parse_args()
    audio_dir = Path(args.audio_dir)
    json_dir = Path(args.json_dir)

    config = None
    if args.config:
        config = config_from_dict(json.loads(Path(args.config).read_text(encoding="utf-8")))

    pairs: list[tuple[Path, Path]] = []
    for json_path in sorted(json_dir.glob("*.json")):
        audio_path = find_audio_for_stem(audio_dir, json_path.stem)
        if audio_path:
            pairs.append((audio_path, json_path))
        if args.max_pairs and len(pairs) >= args.max_pairs:
            break

    xs: list[list[float]] = []
    ys: list[list[float]] = []

    for audio_path, json_path in pairs:
        reference = json.loads(json_path.read_text(encoding="utf-8"))
        predicted = analyze_audio(str(audio_path), config=config)
        ref_segments = reference.get("segments", [])
        pred_segments = predicted.get("segments", [])
        count = min(len(ref_segments), len(pred_segments))
        for idx in range(count):
            ref_vec = ref_segments[idx].get("timbre", [])
            pred_vec = pred_segments[idx].get("timbre", [])
            if len(ref_vec) != len(pred_vec) or not ref_vec:
                continue
            xs.append([float(v) for v in pred_vec])
            ys.append([float(v) for v in ref_vec])

    if not xs:
        raise SystemExit("No paired timbre vectors found.")

    x = np.array(xs, dtype=float)
    y = np.array(ys, dtype=float)
    ones = np.ones((x.shape[0], 1), dtype=float)
    x_aug = np.concatenate([x, ones], axis=1)
    coeffs, _, _, _ = np.linalg.lstsq(x_aug, y, rcond=None)

    matrix = coeffs[:-1, :]
    bias = coeffs[-1, :]

    output: dict[str, Any] = {
        "matrix": matrix.tolist(),
        "bias": bias.tolist(),
        "count": int(x.shape[0]),
    }

    Path(args.output).write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
