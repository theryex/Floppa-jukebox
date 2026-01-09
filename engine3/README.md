# Forever Jukebox Audio Analysis Engine

This package generates analysis JSON compatible with `schema.json` and the Eternal/Infinite Jukebox branch logic.

## Setup

Use Python 3.10 and a virtual environment:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## CLI Usage

Analyze audio to JSON:

```bash
python -m fj_analysis_engine.analyze /path/to/audio.m4a -o /path/to/output.json
```

Analyze with calibration:

```bash
python -m fj_analysis_engine.analyze /path/to/audio.m4a -o /path/to/output.json --calibration calibration.json
```

Compare against benchmark:

```bash
python -m fj_analysis_engine.compare --benchmark-dir benchmark
```

Compare with calibration:

```bash
python -m fj_analysis_engine.compare --benchmark-dir benchmark --calibration calibration.json
```

Calibrate from training data (parallel):

```bash
python -m fj_analysis_engine.calibrate \
  --audio-dir training_data/audio \
  --analysis-dir training_data/analysis \
  -o calibration.json \
  --workers 8
```

Validate an analysis JSON:

```bash
python -m fj_analysis_engine.validate /path/to/output.json
```

## Notes

- ffmpeg must be installed and available in `PATH` for audio decoding.
- The compare command prints similarity plus key sub-scores to stdout.
- Calibration is optional; analysis runs without it.

## Analysis Pipeline (High-Level)

- Decode: `fj_analysis_engine.audio` uses ffmpeg to decode m4a/webm/etc to mono float PCM @ 44.1kHz.
- Beats/Downbeats: `fj_analysis_engine.beats` uses madmom (RNN + DBN) to produce beats + downbeat indices.
- Features: `fj_analysis_engine.features` uses Essentia to compute MFCC, HPCP, and loudness features on frames.
- Segmentation: `fj_analysis_engine.segmentation` builds beat-aware segments from novelty peaks with tunable params.
- Aggregation: `fj_analysis_engine.analysis` summarizes per-segment timbre/pitch/loudness/confidence and assembles sections/bars/beats/tatums/segments.
- Branch Graph: `fj_analysis_engine.jukebox` implements the jremix/go-js overlap and neighbor logic for beat branches.
- Similarity: `fj_analysis_engine.similarity` computes a single similarity % from branch statistics.

## Important Files

- `fj_analysis_engine/analysis.py`: main generator (audio -> analysis JSON).
- `fj_analysis_engine/jukebox.py`: quanta wiring + neighbor distance logic.
- `fj_analysis_engine/similarity.py`: benchmark scoring logic.
- `schema.json`: output schema definition.
- `benchmark/`: gold audio + JSON pair used for compare.
- `training_data/`: paired audio/analysis for calibration.

## Credits

- Eternal/Infinite Jukebox (go-js + jremix logic reference).
- madmom for beat/downbeat tracking.
- Essentia for audio feature extraction.
- librosa, numpy, scipy, soundfile for DSP and numerics.
- OpenAI Codex (implementation assistance).
