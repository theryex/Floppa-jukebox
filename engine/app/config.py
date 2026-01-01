"""Configuration defaults for analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class AnalysisConfig:
    sample_rate: int = 22050
    hop_length: int = 512
    percussive_beats_only: bool = False
    use_librosa_beats: bool = False
    use_laplacian_sections: bool = False
    use_laplacian_segments: bool = False
    use_madmom_downbeats: bool = False
    laplacian_cqt_bins_per_octave: int = 36
    laplacian_cqt_octaves: int = 7
    laplacian_max_clusters: int = 12
    time_signature: int = 4
    tatum_divisions: int = 2
    section_seconds: float = 30.0
    section_use_novelty: bool = True
    section_novelty_percentile: float = 90.0
    section_min_spacing_s: float = 8.0
    section_snap_bar_window_s: float = 0.2
    onset_percentile: float = 75.0
    onset_min_spacing_s: float = 0.05
    tempo_min_bpm: float = 60.0
    tempo_max_bpm: float = 200.0
    beat_snap_window_s: float = 0.07
    segment_min_duration_s: float = 0.05
    timbre_standardize: bool = True
    timbre_scale: float = 10.0
    segment_snap_bar_window_s: float = 0.12
    segment_snap_beat_window_s: float = 0.06
    novelty_smooth_frames: int = 3
    mfcc_window_ms: float = 25.0
    mfcc_hop_ms: float = 10.0
    mfcc_n_mels: int = 40
    mfcc_n_mfcc: int = 12
    mfcc_use_0th: bool = True
    timbre_calibration_matrix: Optional[list[list[float]]] = None
    timbre_calibration_bias: Optional[list[float]] = None
    timbre_mode: str = "mfcc"
    timbre_pca_components: Optional[list[list[float]]] = None
    timbre_pca_mean: Optional[list[float]] = None
    beat_novelty_percentile: float = 75.0
    beat_novelty_min_spacing: int = 1
    timbre_unit_norm: bool = False
    segment_selfsim_kernel_beats: int = 4
    segment_selfsim_percentile: float = 85.0
    segment_selfsim_min_spacing_beats: int = 2
    section_selfsim_kernel_beats: int = 16
    section_selfsim_percentile: float = 80.0
    section_selfsim_min_spacing_beats: int = 8
    section_merge_similarity: float = 0.0
    segment_scalar_scale: Optional[dict[str, float]] = None
    segment_scalar_bias: Optional[dict[str, float]] = None
    pitch_scale: Optional[list[float]] = None
    pitch_bias: Optional[list[float]] = None
    pitch_calibration_matrix: Optional[list[list[float]]] = None
    pitch_calibration_bias: Optional[list[float]] = None
    segment_quantile_maps: Optional[dict[str, dict[str, list[float]]]] = None
    segment_include_bounds: bool = True
    boundary_model_weights: Optional[list[float]] = None
    boundary_model_bias: Optional[float] = None
    boundary_percentile: float = 80.0
    boundary_min_spacing_s: float = 0.05
    start_offset_map_src: Optional[list[float]] = None
    start_offset_map_dst: Optional[list[float]] = None
    target_segment_rate: Optional[float] = None
    target_segment_rate_tolerance: float = 0.1
    target_section_rate: Optional[float] = None
    target_section_rate_tolerance: float = 0.2
    section_include_bounds: bool = True


def config_from_dict(data: dict[str, Any]) -> AnalysisConfig:
    return AnalysisConfig(
        sample_rate=int(data.get("sample_rate", AnalysisConfig.sample_rate)),
        hop_length=int(data.get("hop_length", AnalysisConfig.hop_length)),
        percussive_beats_only=bool(
            data.get("percussive_beats_only", AnalysisConfig.percussive_beats_only)
        ),
        use_librosa_beats=bool(data.get("use_librosa_beats", AnalysisConfig.use_librosa_beats)),
        use_laplacian_sections=bool(
            data.get("use_laplacian_sections", AnalysisConfig.use_laplacian_sections)
        ),
        use_laplacian_segments=bool(
            data.get("use_laplacian_segments", AnalysisConfig.use_laplacian_segments)
        ),
        use_madmom_downbeats=bool(
            data.get("use_madmom_downbeats", AnalysisConfig.use_madmom_downbeats)
        ),
        laplacian_cqt_bins_per_octave=int(
            data.get("laplacian_cqt_bins_per_octave", AnalysisConfig.laplacian_cqt_bins_per_octave)
        ),
        laplacian_cqt_octaves=int(
            data.get("laplacian_cqt_octaves", AnalysisConfig.laplacian_cqt_octaves)
        ),
        laplacian_max_clusters=int(
            data.get("laplacian_max_clusters", AnalysisConfig.laplacian_max_clusters)
        ),
        time_signature=int(data.get("time_signature", AnalysisConfig.time_signature)),
        tatum_divisions=int(data.get("tatum_divisions", AnalysisConfig.tatum_divisions)),
        section_seconds=float(data.get("section_seconds", AnalysisConfig.section_seconds)),
        section_use_novelty=bool(data.get("section_use_novelty", AnalysisConfig.section_use_novelty)),
        section_novelty_percentile=float(
            data.get("section_novelty_percentile", AnalysisConfig.section_novelty_percentile)
        ),
        section_min_spacing_s=float(data.get("section_min_spacing_s", AnalysisConfig.section_min_spacing_s)),
        section_snap_bar_window_s=float(data.get("section_snap_bar_window_s", AnalysisConfig.section_snap_bar_window_s)),
        onset_percentile=float(data.get("onset_percentile", AnalysisConfig.onset_percentile)),
        onset_min_spacing_s=float(data.get("onset_min_spacing_s", AnalysisConfig.onset_min_spacing_s)),
        tempo_min_bpm=float(data.get("tempo_min_bpm", AnalysisConfig.tempo_min_bpm)),
        tempo_max_bpm=float(data.get("tempo_max_bpm", AnalysisConfig.tempo_max_bpm)),
        beat_snap_window_s=float(data.get("beat_snap_window_s", AnalysisConfig.beat_snap_window_s)),
        segment_min_duration_s=float(data.get("segment_min_duration_s", AnalysisConfig.segment_min_duration_s)),
        timbre_standardize=bool(data.get("timbre_standardize", AnalysisConfig.timbre_standardize)),
        timbre_scale=float(data.get("timbre_scale", AnalysisConfig.timbre_scale)),
        segment_snap_bar_window_s=float(data.get("segment_snap_bar_window_s", AnalysisConfig.segment_snap_bar_window_s)),
        segment_snap_beat_window_s=float(data.get("segment_snap_beat_window_s", AnalysisConfig.segment_snap_beat_window_s)),
        novelty_smooth_frames=int(data.get("novelty_smooth_frames", AnalysisConfig.novelty_smooth_frames)),
        mfcc_window_ms=float(data.get("mfcc_window_ms", AnalysisConfig.mfcc_window_ms)),
        mfcc_hop_ms=float(data.get("mfcc_hop_ms", AnalysisConfig.mfcc_hop_ms)),
        mfcc_n_mels=int(data.get("mfcc_n_mels", AnalysisConfig.mfcc_n_mels)),
        mfcc_n_mfcc=int(data.get("mfcc_n_mfcc", AnalysisConfig.mfcc_n_mfcc)),
        mfcc_use_0th=bool(data.get("mfcc_use_0th", AnalysisConfig.mfcc_use_0th)),
        timbre_calibration_matrix=data.get("timbre_calibration_matrix", AnalysisConfig.timbre_calibration_matrix),
        timbre_calibration_bias=data.get("timbre_calibration_bias", AnalysisConfig.timbre_calibration_bias),
        timbre_mode=str(data.get("timbre_mode", AnalysisConfig.timbre_mode)),
        timbre_pca_components=data.get("timbre_pca_components", AnalysisConfig.timbre_pca_components),
        timbre_pca_mean=data.get("timbre_pca_mean", AnalysisConfig.timbre_pca_mean),
        beat_novelty_percentile=float(data.get("beat_novelty_percentile", AnalysisConfig.beat_novelty_percentile)),
        beat_novelty_min_spacing=int(data.get("beat_novelty_min_spacing", AnalysisConfig.beat_novelty_min_spacing)),
        timbre_unit_norm=bool(data.get("timbre_unit_norm", AnalysisConfig.timbre_unit_norm)),
        segment_selfsim_kernel_beats=int(
            data.get("segment_selfsim_kernel_beats", AnalysisConfig.segment_selfsim_kernel_beats)
        ),
        segment_selfsim_percentile=float(
            data.get("segment_selfsim_percentile", AnalysisConfig.segment_selfsim_percentile)
        ),
        segment_selfsim_min_spacing_beats=int(
            data.get("segment_selfsim_min_spacing_beats", AnalysisConfig.segment_selfsim_min_spacing_beats)
        ),
        section_selfsim_kernel_beats=int(
            data.get("section_selfsim_kernel_beats", AnalysisConfig.section_selfsim_kernel_beats)
        ),
        section_selfsim_percentile=float(
            data.get("section_selfsim_percentile", AnalysisConfig.section_selfsim_percentile)
        ),
        section_selfsim_min_spacing_beats=int(
            data.get("section_selfsim_min_spacing_beats", AnalysisConfig.section_selfsim_min_spacing_beats)
        ),
        section_merge_similarity=float(
            data.get("section_merge_similarity", AnalysisConfig.section_merge_similarity)
        ),
        segment_scalar_scale=data.get("segment_scalar_scale", AnalysisConfig.segment_scalar_scale),
        segment_scalar_bias=data.get("segment_scalar_bias", AnalysisConfig.segment_scalar_bias),
        pitch_scale=data.get("pitch_scale", AnalysisConfig.pitch_scale),
        pitch_bias=data.get("pitch_bias", AnalysisConfig.pitch_bias),
        pitch_calibration_matrix=data.get("pitch_calibration_matrix", AnalysisConfig.pitch_calibration_matrix),
        pitch_calibration_bias=data.get("pitch_calibration_bias", AnalysisConfig.pitch_calibration_bias),
        segment_quantile_maps=data.get("segment_quantile_maps", AnalysisConfig.segment_quantile_maps),
        segment_include_bounds=bool(data.get("segment_include_bounds", AnalysisConfig.segment_include_bounds)),
        boundary_model_weights=data.get("boundary_model_weights", AnalysisConfig.boundary_model_weights),
        boundary_model_bias=data.get("boundary_model_bias", AnalysisConfig.boundary_model_bias),
        boundary_percentile=float(data.get("boundary_percentile", AnalysisConfig.boundary_percentile)),
        boundary_min_spacing_s=float(data.get("boundary_min_spacing_s", AnalysisConfig.boundary_min_spacing_s)),
        start_offset_map_src=data.get("start_offset_map_src", AnalysisConfig.start_offset_map_src),
        start_offset_map_dst=data.get("start_offset_map_dst", AnalysisConfig.start_offset_map_dst),
        target_segment_rate=data.get("target_segment_rate", AnalysisConfig.target_segment_rate),
        target_segment_rate_tolerance=float(
            data.get("target_segment_rate_tolerance", AnalysisConfig.target_segment_rate_tolerance)
        ),
        target_section_rate=data.get("target_section_rate", AnalysisConfig.target_section_rate),
        target_section_rate_tolerance=float(
            data.get("target_section_rate_tolerance", AnalysisConfig.target_section_rate_tolerance)
        ),
        section_include_bounds=bool(data.get("section_include_bounds", AnalysisConfig.section_include_bounds)),
    )
