import { beforeEach, describe, expect, it, vi } from "vitest";
import { CanvasViz } from "./CanvasViz";
import { setWindowUrl } from "../app/__tests__/test-utils";

type Listener = (event: MouseEvent) => void;

function createMockCtx() {
  return {
    setTransform: vi.fn(),
    clearRect: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    beginPath: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    stroke: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    quadraticCurveTo: vi.fn(),
    lineWidth: 0,
    fillStyle: "",
    strokeStyle: "",
  } as unknown as CanvasRenderingContext2D;
}

function createMockCanvas(ctx: CanvasRenderingContext2D) {
  const listeners = new Map<string, Listener>();
  return {
    style: {},
    width: 0,
    height: 0,
    getContext: vi.fn(() => ctx),
    addEventListener: vi.fn((type: string, handler: Listener) => {
      listeners.set(type, handler);
    }),
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 200, height: 200 }),
    _listeners: listeners,
  } as unknown as HTMLCanvasElement & { _listeners: Map<string, Listener> };
}

function createMockDocument() {
  const baseCtx = createMockCtx();
  const overlayCtx = createMockCtx();
  const canvases = [
    createMockCanvas(baseCtx),
    createMockCanvas(overlayCtx),
  ];
  let index = 0;
  const documentMock = {
    documentElement: {},
    createElement: vi.fn(() => canvases[index++]),
  };
  return { documentMock, baseCtx, overlayCtx, canvases };
}

function createContainer() {
  return {
    append: vi.fn(),
    getBoundingClientRect: () => ({ width: 200, height: 200 }),
  } as unknown as HTMLElement;
}

describe("CanvasViz", () => {
  beforeEach(() => {
    setWindowUrl("http://localhost/");
    const { documentMock } = createMockDocument();
    (globalThis as any).document = documentMock;
    (globalThis as any).getComputedStyle = () => ({
      getPropertyValue: () => "",
    });
    (globalThis as any).window.devicePixelRatio = 1;
  });

  it("draws beats and edges on setData", () => {
    const { documentMock, baseCtx } = createMockDocument();
    (globalThis as any).document = documentMock;
    const container = createContainer();
    const positioner = () => [
      { x: 10, y: 10 },
      { x: 100, y: 10 },
    ];
    const viz = new CanvasViz(container, positioner);
    viz.setData({
      beats: [{ which: 0 }, { which: 1 }] as any,
      edges: [
        { src: { which: 0 }, dest: { which: 1 }, deleted: false } as any,
      ],
    });
    expect((baseCtx as any).clearRect).toHaveBeenCalled();
    expect((baseCtx as any).arc).toHaveBeenCalled();
    expect((baseCtx as any).stroke).toHaveBeenCalled();
  });

  it("selects a beat on click", () => {
    const { documentMock, canvases } = createMockDocument();
    (globalThis as any).document = documentMock;
    const container = createContainer();
    const positioner = () => [{ x: 10, y: 10 }];
    const viz = new CanvasViz(container, positioner);
    const onSelect = vi.fn();
    viz.setOnSelect(onSelect);
    viz.setData({ beats: [{ which: 0 }], edges: [] } as any);
    const handler = canvases[1]._listeners.get("click");
    handler?.({ clientX: 12, clientY: 12 } as MouseEvent);
    expect(onSelect).toHaveBeenCalledWith(0);
  });

  it("selects an edge on click when no beat selection", () => {
    const { documentMock, canvases } = createMockDocument();
    (globalThis as any).document = documentMock;
    const container = createContainer();
    const positioner = () => [
      { x: 10, y: 10 },
      { x: 100, y: 10 },
    ];
    const viz = new CanvasViz(container, positioner);
    const onEdgeSelect = vi.fn();
    viz.setOnEdgeSelect(onEdgeSelect);
    viz.setData({
      beats: [{ which: 0 }, { which: 1 }] as any,
      edges: [
        { src: { which: 0 }, dest: { which: 1 }, deleted: false } as any,
      ],
    });
    const handler = canvases[1]._listeners.get("click");
    handler?.({ clientX: 55, clientY: 10 } as MouseEvent);
    expect(onEdgeSelect).toHaveBeenCalled();
  });
});
