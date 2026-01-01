import { describe, expect, it } from "vitest";
import { selectNextBeatIndex } from "./selection";
import { JukeboxConfig, JukeboxGraphState, QuantumBase } from "./types";

function makeBeat(which: number): QuantumBase {
  return {
    start: which,
    duration: 1,
    which,
    prev: null,
    next: null,
    overlappingSegments: [],
    neighbors: [],
    allNeighbors: [],
  };
}

describe("selectNextBeatIndex", () => {
  it("forces a branch at the last branch point", () => {
    const seed = makeBeat(1);
    const target = makeBeat(0);
    seed.neighbors.push({
      id: 0,
      src: seed,
      dest: target,
      distance: 10,
      deleted: false,
    });
    const config: JukeboxConfig = {
      maxBranches: 4,
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
    const graph: JukeboxGraphState = {
      computedThreshold: 60,
      currentThreshold: 60,
      lastBranchPoint: 1,
      totalBeats: 2,
      longestReach: 0,
      allEdges: [],
    };
    const selection = selectNextBeatIndex(
      seed,
      graph,
      config,
      () => 0.99,
      { curRandomBranchChance: 0.18 }
    );
    expect(selection.index).toBe(0);
    expect(selection.jumped).toBe(true);
  });

  it("branches when random chance triggers", () => {
    const seed = makeBeat(1);
    const target = makeBeat(2);
    seed.neighbors.push({
      id: 0,
      src: seed,
      dest: target,
      distance: 10,
      deleted: false,
    });
    const config: JukeboxConfig = {
      maxBranches: 4,
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
    const graph: JukeboxGraphState = {
      computedThreshold: 60,
      currentThreshold: 60,
      lastBranchPoint: 99,
      totalBeats: 2,
      longestReach: 0,
      allEdges: [],
    };
    const selection = selectNextBeatIndex(
      seed,
      graph,
      config,
      () => 0.1,
      { curRandomBranchChance: 0.18 }
    );
    expect(selection.index).toBe(2);
    expect(selection.jumped).toBe(true);
  });
});
