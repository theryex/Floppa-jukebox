import { describe, expect, it } from "vitest";
import { normalizeAnalysis } from "./analysis";
import { buildJumpGraph } from "./graph";
import { JukeboxConfig } from "./types";

function makeAnalysis() {
  return {
    sections: [{ start: 0, duration: 4, confidence: 1 }],
    bars: [
      { start: 0, duration: 2, confidence: 0.8 },
      { start: 2, duration: 2, confidence: 0.8 },
    ],
    beats: [
      { start: 0, duration: 1, confidence: 0.6 },
      { start: 1, duration: 1, confidence: 0.6 },
      { start: 2, duration: 1, confidence: 0.6 },
      { start: 3, duration: 1, confidence: 0.6 },
    ],
    tatums: [
      { start: 0, duration: 0.5, confidence: 0.5 },
      { start: 0.5, duration: 0.5, confidence: 0.5 },
      { start: 1, duration: 0.5, confidence: 0.5 },
      { start: 1.5, duration: 0.5, confidence: 0.5 },
    ],
    segments: [
      {
        start: 0,
        duration: 1,
        confidence: 0.4,
        loudness_start: -20,
        loudness_max: -5,
        loudness_max_time: 0.2,
        pitches: new Array(12).fill(0.5),
        timbre: new Array(12).fill(1),
      },
      {
        start: 1,
        duration: 1,
        confidence: 0.4,
        loudness_start: -19,
        loudness_max: -5,
        loudness_max_time: 0.2,
        pitches: new Array(12).fill(0.51),
        timbre: new Array(12).fill(1.1),
      },
      {
        start: 2,
        duration: 1,
        confidence: 0.4,
        loudness_start: -18,
        loudness_max: -4.5,
        loudness_max_time: 0.2,
        pitches: new Array(12).fill(0.52),
        timbre: new Array(12).fill(1.2),
      },
      {
        start: 3,
        duration: 1,
        confidence: 0.4,
        loudness_start: -17,
        loudness_max: -4.2,
        loudness_max_time: 0.2,
        pitches: new Array(12).fill(0.53),
        timbre: new Array(12).fill(1.3),
      },
    ],
    track: { duration: 4 },
  };
}

describe("buildJumpGraph", () => {
  it("builds neighbors and a last branch point", () => {
    const analysis = normalizeAnalysis(makeAnalysis());
    const config: JukeboxConfig = {
      maxBranches: 3,
      maxBranchThreshold: 80,
      currentThreshold: 60,
      addLastEdge: true,
      justBackwards: false,
      justLongBranches: false,
      removeSequentialBranches: false,
      minRandomBranchChance: 0.18,
      maxRandomBranchChance: 0.5,
      randomBranchChanceDelta: 0.018,
      minLongBranch: 1,
    };
    const graph = buildJumpGraph(analysis, config);
    expect(graph.totalBeats).toBe(4);
    expect(graph.lastBranchPoint).toBeGreaterThanOrEqual(0);
    expect(analysis.beats.some((beat) => beat.neighbors.length > 0)).toBe(true);
  });
});
