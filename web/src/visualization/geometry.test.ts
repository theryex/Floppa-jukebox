import { describe, expect, it } from "vitest";
import { distanceToQuadratic, distanceToSegment } from "./geometry";

describe("geometry", () => {
  it("computes distance to a segment", () => {
    expect(distanceToSegment(0, 0, 0, 0, 10, 0)).toBe(0);
    expect(distanceToSegment(5, 5, 0, 0, 10, 0)).toBe(5);
    expect(distanceToSegment(-5, 0, 0, 0, 10, 0)).toBe(5);
  });

  it("handles zero-length segment", () => {
    expect(distanceToSegment(3, 4, 0, 0, 0, 0)).toBe(5);
  });

  it("computes distance to quadratic curve", () => {
    const distOnCurve = distanceToQuadratic(0, 0, 0, 0, 5, 5, 10, 0);
    expect(distOnCurve).toBeLessThan(0.01);
    const distNearCurve = distanceToQuadratic(5, 5, 0, 0, 5, 5, 10, 0);
    expect(distNearCurve).toBeCloseTo(2.5, 1);
  });
});
