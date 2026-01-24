import { beforeEach, describe, expect, it, vi } from "vitest";
import { attachVisualizationResize, createVisualizations } from "./visualization";
import { setWindowUrl } from "./__tests__/test-utils";

vi.mock("../visualization/CanvasViz", () => {
  return {
    CanvasViz: class {
      layer: HTMLElement;
      positioner: (count: number, width: number, height: number) => Array<{
        x: number;
        y: number;
      }>;
      resizeNow = vi.fn();
      constructor(
        layer: HTMLElement,
        positioner: (count: number, width: number, height: number) => Array<{
          x: number;
          y: number;
        }>,
      ) {
        this.layer = layer;
        this.positioner = positioner;
      }
    },
  };
});

describe("visualization helpers", () => {
  beforeEach(() => {
    setWindowUrl("http://localhost/");
  });

  it("creates visualization instances with positioners", () => {
    const layer = {} as HTMLElement;
    const viz = createVisualizations(layer);
    expect(viz.length).toBe(6);
    const first = viz[0] as unknown as { positioner: Function };
    const points = first.positioner(3, 100, 100);
    expect(points.length).toBe(3);
  });

  it("attaches resize observer when available", () => {
    const observe = vi.fn();
    (globalThis as any).ResizeObserver = class {
      constructor(cb: () => void) {
        cb();
      }
      observe = observe;
    };
    const viz = [{ resizeNow: vi.fn() }] as any;
    attachVisualizationResize(viz, {} as HTMLElement);
    expect(observe).toHaveBeenCalled();
  });

  it("falls back to window resize listener", () => {
    (globalThis as any).ResizeObserver = undefined;
    (globalThis.window as any).addEventListener = vi.fn();
    const viz = [{ resizeNow: vi.fn() }] as any;
    attachVisualizationResize(viz, {} as HTMLElement);
    expect(window.addEventListener).toHaveBeenCalledWith(
      "resize",
      expect.any(Function),
    );
  });
});
