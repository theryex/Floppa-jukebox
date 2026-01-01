import { describe, expect, it } from "vitest";
import { normalizeAnalysis } from "./analysis";

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

describe("normalizeAnalysis", () => {
  it("links quanta and overlapping segments", () => {
    const analysis = normalizeAnalysis(makeAnalysis());
    expect(analysis.beats.length).toBe(4);
    expect(analysis.beats[0].next?.which).toBe(1);
    expect(analysis.beats[0].overlappingSegments.length).toBeGreaterThan(0);
  });
});
