import argparse
import json
from pathlib import Path

from .analysis import analyze_audio
from .similarity import compare_analysis


AUDIO_EXTS = {".m4a", ".webm", ".mp3", ".wav", ".flac", ".ogg"}


def find_benchmark(benchmark_dir: Path) -> tuple[Path, Path]:
    audio_path = None
    json_path = None
    for p in benchmark_dir.iterdir():
        if p.suffix.lower() in AUDIO_EXTS:
            audio_path = p
        elif p.suffix.lower() == ".json":
            json_path = p
    if not audio_path or not json_path:
        raise FileNotFoundError("benchmark directory must contain one audio file and one JSON")
    return audio_path, json_path


def load_analysis(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if "analysis" in data:
        return data["analysis"]
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare analysis vs benchmark gold")
    parser.add_argument("--benchmark-dir", required=True)
    parser.add_argument("--calibration", default=None)
    args = parser.parse_args()

    benchmark_dir = Path(args.benchmark_dir)
    audio_path, json_path = find_benchmark(benchmark_dir)

    generated = analyze_audio(str(audio_path), calibration_path=args.calibration)
    gold = load_analysis(json_path)

    result = compare_analysis(gold, generated)

    print(f"similarity={result['similarity']:.2f}%")
    print(f"threshold score={result['scores']['threshold']:.3f}")
    print(f"branching score={result['scores']['branching']:.3f}")
    print(f"histogram score={result['scores']['histogram']:.3f}")
    print(f"edges score={result['scores']['edges']:.3f}")
    print(f"gold threshold={result['gold']['computed_threshold']}")
    print(f"gen threshold={result['generated']['computed_threshold']}")
    print(f"gold branching={result['gold']['branching_fraction']:.3f}")
    print(f"gen branching={result['generated']['branching_fraction']:.3f}")
    print(f"gold hist={result['gold']['neighbor_hist']}")
    print(f"gen hist={result['generated']['neighbor_hist']}")
    print(f"gold median distance={result['gold']['median_distance']:.3f}")
    print(f"gen median distance={result['generated']['median_distance']:.3f}")


if __name__ == "__main__":
    main()
