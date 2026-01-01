import { Edge, QuantumBase } from "../engine/types";

interface VisualizationData {
  beats: QuantumBase[];
  edges: Edge[];
}

interface JumpLine {
  from: number;
  to: number;
  at: number;
}

export type Positioner = (
  count: number,
  width: number,
  height: number
) => Array<{ x: number; y: number }>;

export class CanvasViz {
  private container: HTMLElement;
  private baseCanvas: HTMLCanvasElement;
  private overlayCanvas: HTMLCanvasElement;
  private baseCtx: CanvasRenderingContext2D;
  private overlayCtx: CanvasRenderingContext2D;
  private positions: Array<{ x: number; y: number }> = [];
  private data: VisualizationData | null = null;
  private currentIndex = -1;
  private jumpLine: JumpLine | null = null;
  private onSelect: ((index: number) => void) | null = null;
  private onEdgeSelect: ((edge: Edge | null) => void) | null = null;
  private selectedEdge: Edge | null = null;
  private center = { x: 0, y: 0 };
  private positioner: Positioner;
  private visible = true;

  constructor(container: HTMLElement, positioner: Positioner) {
    this.container = container;
    this.positioner = positioner;
    this.baseCanvas = document.createElement("canvas");
    this.overlayCanvas = document.createElement("canvas");
    const baseCtx = this.baseCanvas.getContext("2d");
    const overlayCtx = this.overlayCanvas.getContext("2d");
    if (!baseCtx || !overlayCtx) {
      throw new Error("Canvas not supported");
    }
    this.baseCtx = baseCtx;
    this.overlayCtx = overlayCtx;
    this.container.append(this.baseCanvas, this.overlayCanvas);
    this.applyCanvasStyles();
    this.resize();
    window.addEventListener("resize", () => this.resize());
    this.overlayCanvas.addEventListener("click", (event) =>
      this.handleClick(event)
    );
  }

  setVisible(visible: boolean) {
    this.visible = visible;
    const display = visible ? "block" : "none";
    this.baseCanvas.style.display = display;
    this.overlayCanvas.style.display = display;
    if (visible && this.data) {
      this.drawBase();
      this.drawOverlay();
    }
  }

  setData(data: VisualizationData) {
    this.data = data;
    this.computePositions();
    this.drawBase();
    this.drawOverlay();
  }

  refresh() {
    if (!this.data) {
      return;
    }
    this.drawBase();
    this.drawOverlay();
  }

  update(currentIndex: number, lastJumped: boolean, previousIndex: number | null) {
    this.currentIndex = currentIndex;
    if (lastJumped && previousIndex !== null) {
      this.jumpLine = {
        from: previousIndex,
        to: currentIndex,
        at: performance.now(),
      };
    }
    this.drawOverlay();
  }

  reset() {
    this.currentIndex = -1;
    this.jumpLine = null;
    this.selectedEdge = null;
    this.drawOverlay();
  }

  setOnSelect(handler: (index: number) => void) {
    this.onSelect = handler;
  }

  setOnEdgeSelect(handler: (edge: Edge | null) => void) {
    this.onEdgeSelect = handler;
  }

  setSelectedEdge(edge: Edge | null) {
    this.selectedEdge = edge;
    this.drawOverlay();
  }

  resizeNow() {
    this.resize();
  }

  private applyCanvasStyles() {
    this.baseCanvas.style.position = "absolute";
    this.baseCanvas.style.inset = "0";
    this.baseCanvas.style.width = "100%";
    this.baseCanvas.style.height = "100%";
    this.overlayCanvas.style.position = "absolute";
    this.overlayCanvas.style.inset = "0";
    this.overlayCanvas.style.width = "100%";
    this.overlayCanvas.style.height = "100%";
  }

  private resize() {
    const rect = this.container.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) {
      return;
    }
    const dpr = window.devicePixelRatio || 1;
    this.baseCanvas.width = rect.width * dpr;
    this.baseCanvas.height = rect.height * dpr;
    this.overlayCanvas.width = rect.width * dpr;
    this.overlayCanvas.height = rect.height * dpr;
    this.baseCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.overlayCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (this.data) {
      this.computePositions();
      this.drawBase();
      this.drawOverlay();
    }
  }

  private computePositions() {
    if (!this.data) {
      return;
    }
    const { width, height } = this.container.getBoundingClientRect();
    this.positions = this.positioner(this.data.beats.length, width, height);
    this.center = { x: width / 2, y: height / 2 };
  }

  private drawBase() {
    if (!this.data || !this.visible) {
      return;
    }
    const { width, height } = this.container.getBoundingClientRect();
    this.baseCtx.clearRect(0, 0, width, height);
    this.baseCtx.save();
    this.baseCtx.lineWidth = 1;

    const edges = this.data.edges;
    const maxEdges = 2500;
    const step = edges.length > maxEdges ? Math.ceil(edges.length / maxEdges) : 1;

    const edgeStroke =
      getComputedStyle(document.body).getPropertyValue("--edge-stroke").trim() ||
      "rgba(74, 199, 255, 0.12)";
    for (let i = 0; i < edges.length; i += step) {
      const edge = edges[i];
      if (edge.deleted) {
        continue;
      }
      this.drawEdge(this.baseCtx, edge, edgeStroke, 1);
    }

    const beatFill =
      getComputedStyle(document.body).getPropertyValue("--beat-fill").trim() ||
      "rgba(255, 215, 130, 0.55)";
    this.baseCtx.fillStyle = beatFill;
    for (let i = 0; i < this.positions.length; i += 1) {
      const p = this.positions[i];
      this.baseCtx.beginPath();
      this.baseCtx.arc(p.x, p.y, 2, 0, Math.PI * 2);
      this.baseCtx.fill();
    }
    this.baseCtx.restore();
  }

  private drawOverlay() {
    const { width, height } = this.container.getBoundingClientRect();
    this.overlayCtx.clearRect(0, 0, width, height);
    if (!this.data || !this.visible) {
      return;
    }
    if (this.selectedEdge && !this.selectedEdge.deleted) {
      const edgeSelected =
        getComputedStyle(document.body).getPropertyValue("--edge-selected").trim() ||
        "#ff5b5b";
      this.drawEdge(this.overlayCtx, this.selectedEdge, edgeSelected, 2.5);
    }
    if (this.currentIndex < 0) {
      return;
    }
    const current = this.positions[this.currentIndex];
    if (current) {
      const beatHighlight =
        getComputedStyle(document.body).getPropertyValue("--beat-highlight").trim() ||
        "#ffd46a";
      this.overlayCtx.fillStyle = beatHighlight;
      this.overlayCtx.beginPath();
      this.overlayCtx.arc(current.x, current.y, 6, 0, Math.PI * 2);
      this.overlayCtx.fill();
    }
    if (this.jumpLine) {
      const age = performance.now() - this.jumpLine.at;
      if (age < 1000) {
        const from = this.positions[this.jumpLine.from];
        const to = this.positions[this.jumpLine.to];
        if (from && to) {
          const alpha = 1 - age / 1000;
          const jumpRgb =
            getComputedStyle(document.body).getPropertyValue("--beat-jump-rgb").trim() ||
            "255, 212, 106";
          const jumpColor = `rgba(${jumpRgb}, ${alpha})`;
          if (this.shouldBendEdge(from, to)) {
            this.drawBentLine(this.overlayCtx, from, to, jumpColor, 2);
          } else {
            this.overlayCtx.strokeStyle = jumpColor;
            this.overlayCtx.lineWidth = 2;
            this.overlayCtx.beginPath();
            this.overlayCtx.moveTo(from.x, from.y);
            this.overlayCtx.lineTo(to.x, to.y);
            this.overlayCtx.stroke();
          }
        }
      } else {
        this.jumpLine = null;
      }
    }
  }

  private handleClick(event: MouseEvent) {
    if (!this.data || !this.visible) {
      return;
    }
    const rect = this.overlayCanvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    if (this.onSelect) {
      const maxDistance = 8;
      let bestIndex = -1;
      let bestDist = Infinity;
      for (let i = 0; i < this.positions.length; i += 1) {
        const p = this.positions[i];
        const dx = p.x - x;
        const dy = p.y - y;
        const d = Math.sqrt(dx * dx + dy * dy);
        if (d < bestDist) {
          bestDist = d;
          bestIndex = i;
        }
      }
      if (bestIndex >= 0 && bestDist <= maxDistance) {
        this.onSelect(bestIndex);
        return;
      }
    }
    if (this.onEdgeSelect) {
      const edgeThreshold = 8;
      let bestEdge: Edge | null = null;
      let bestEdgeDist = Infinity;
      for (const edge of this.data.edges) {
        if (edge.deleted) {
          continue;
        }
        const from = this.positions[edge.src.which];
        const to = this.positions[edge.dest.which];
        if (!from || !to) {
          continue;
        }
        const dist = this.shouldBendEdge(from, to)
          ? distanceToQuadratic(
              x,
              y,
              from.x,
              from.y,
              ...this.getBendControlPoint(from, to),
              to.x,
              to.y
            )
          : distanceToSegment(x, y, from.x, from.y, to.x, to.y);
        if (dist < bestEdgeDist) {
          bestEdgeDist = dist;
          bestEdge = edge;
        }
      }
      if (bestEdge && bestEdgeDist <= edgeThreshold) {
        const nextEdge = this.selectedEdge === bestEdge ? null : bestEdge;
        this.onEdgeSelect(nextEdge);
      }
    }
  }

  private drawEdge(
    ctx: CanvasRenderingContext2D,
    edge: Edge,
    color: string,
    lineWidth: number
  ) {
    const from = this.positions[edge.src.which];
    const to = this.positions[edge.dest.which];
    if (!from || !to) {
      return;
    }
    if (this.shouldBendEdge(from, to)) {
      this.drawBentLine(ctx, from, to, color, lineWidth);
      return;
    }
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x, to.y);
    ctx.stroke();
  }

  private shouldBendEdge(from: { x: number; y: number }, to: { x: number; y: number }) {
    const beatAvoid = 6;
    const maxSamples = 300;
    const step = Math.max(1, Math.ceil(this.positions.length / maxSamples));
    for (let i = 0; i < this.positions.length; i += step) {
      const p = this.positions[i];
      if (!p) {
        continue;
      }
      if ((p.x === from.x && p.y === from.y) || (p.x === to.x && p.y === to.y)) {
        continue;
      }
      const dist = distanceToSegment(p.x, p.y, from.x, from.y, to.x, to.y);
      if (dist <= beatAvoid) {
        return true;
      }
    }
    return false;
  }

  private drawBentLine(
    ctx: CanvasRenderingContext2D,
    from: { x: number; y: number },
    to: { x: number; y: number },
    color: string,
    lineWidth: number
  ) {
    const [cx, cy] = this.getBendControlPoint(from, to);
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.quadraticCurveTo(cx, cy, to.x, to.y);
    ctx.stroke();
  }

  private getBendControlPoint(
    from: { x: number; y: number },
    to: { x: number; y: number }
  ): [number, number] {
    const mid = { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 };
    const dirX = this.center.x - mid.x;
    const dirY = this.center.y - mid.y;
    const dirLen = Math.hypot(dirX, dirY);
    if (dirLen === 0) {
      return [mid.x, mid.y];
    }
    const normX = dirX / dirLen;
    const normY = dirY / dirLen;
    const centerDist = Math.hypot(this.center.x - mid.x, this.center.y - mid.y);
    return [
      mid.x + normX * (centerDist * 0.5),
      mid.y + normY * (centerDist * 0.5),
    ];
  }
}

function distanceToSegment(
  px: number,
  py: number,
  x1: number,
  y1: number,
  x2: number,
  y2: number
): number {
  const dx = x2 - x1;
  const dy = y2 - y1;
  if (dx === 0 && dy === 0) {
    const sx = px - x1;
    const sy = py - y1;
    return Math.sqrt(sx * sx + sy * sy);
  }
  const t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy);
  const clamped = Math.max(0, Math.min(1, t));
  const cx = x1 + clamped * dx;
  const cy = y1 + clamped * dy;
  const ex = px - cx;
  const ey = py - cy;
  return Math.sqrt(ex * ex + ey * ey);
}

function distanceToQuadratic(
  px: number,
  py: number,
  x1: number,
  y1: number,
  cx: number,
  cy: number,
  x2: number,
  y2: number
): number {
  const samples = 24;
  let best = Infinity;
  let prevX = x1;
  let prevY = y1;
  for (let i = 1; i <= samples; i += 1) {
    const t = i / samples;
    const mt = 1 - t;
    const qx = mt * mt * x1 + 2 * mt * t * cx + t * t * x2;
    const qy = mt * mt * y1 + 2 * mt * t * cy + t * t * y2;
    const dist = distanceToSegment(px, py, prevX, prevY, qx, qy);
    if (dist < best) {
      best = dist;
    }
    prevX = qx;
    prevY = qy;
  }
  return best;
}
