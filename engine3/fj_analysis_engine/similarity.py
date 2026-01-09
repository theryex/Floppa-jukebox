from typing import Dict, Any

import numpy as np

from .jukebox import compute_branch_stats


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def compare_analysis(gold: Dict[str, Any], generated: Dict[str, Any]) -> Dict[str, Any]:
    gold_stats = compute_branch_stats(gold)
    gen_stats = compute_branch_stats(generated)

    tg = gold_stats["computed_threshold"]
    tr = gen_stats["computed_threshold"]
    bg = gold_stats["branching_fraction"]
    br = gen_stats["branching_fraction"]
    hg = np.asarray(gold_stats["neighbor_hist"], dtype=float)
    hr = np.asarray(gen_stats["neighbor_hist"], dtype=float)
    mg = gold_stats["median_distance"]
    mr = gen_stats["median_distance"]

    score_thresh = 1.0 - clamp(abs(tg - tr) / 20.0, 0.0, 1.0)
    score_branch = 1.0 - clamp(abs(bg - br) / 0.25, 0.0, 1.0)
    score_hist = 1.0 - clamp(float(np.sum(np.abs(hg - hr))) / 2.0, 0.0, 1.0)
    score_edges = 1.0 - clamp(abs(mg - mr) / 40.0, 0.0, 1.0)

    similarity = 100.0 * (
        0.35 * score_hist
        + 0.25 * score_branch
        + 0.25 * score_thresh
        + 0.15 * score_edges
    )

    return {
        "similarity": similarity,
        "scores": {
            "threshold": score_thresh,
            "branching": score_branch,
            "histogram": score_hist,
            "edges": score_edges,
        },
        "gold": gold_stats,
        "generated": gen_stats,
    }
