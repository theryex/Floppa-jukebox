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

export class JukeboxRing {
  private container: HTMLElement;
  private baseCanvas: HTMLCanvasElement;
  private overlayCanvas: HTMLCanvasElement;
  private baseCtx: CanvasRenderingContext2D;
  private overlayCtx: CanvasRenderingContext2D;
  private positions: Array<{ x: number; y: number }> = [];
  private ringRadius = 0;
  private data: VisualizationData | null = null;
  private currentIndex = -1;
  private jumpLine: JumpLine | null = null;
  private onSelect: ((index: number) => void) | null = null;

  constructor(container: HTMLElement) {
    this.container = container;
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
    this.resize();
    window.addEventListener("resize", () => this.resize());
    this.overlayCanvas.addEventListener("click", (event) =>
      this.handleClick(event)
    );
  }

  resizeNow() {
    this.resize();
  }

  refresh() {
    if (!this.data) {
      return;
    }
    this.drawBase();
    this.drawOverlay();
  }

  setData(data: VisualizationData) {
    this.data = data;
    this.computePositions();
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
    this.drawOverlay();
  }

  setOnSelect(handler: (index: number) => void) {
    this.onSelect = handler;
  }

  private resize() {
    const rect = this.container.getBoundingClientRect();
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
    const radius = Math.min(width, height) * 0.4;
    this.ringRadius = radius;
    const cx = width / 2;
    const cy = height / 2;
    const count = this.data.beats.length;
    this.positions = [];
    for (let i = 0; i < count; i += 1) {
      const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
      this.positions.push({
        x: cx + Math.cos(angle) * radius,
        y: cy + Math.sin(angle) * radius,
      });
    }
  }

  private drawBase() {
    if (!this.data) {
      return;
    }
    const { width, height } = this.container.getBoundingClientRect();
    this.baseCtx.clearRect(0, 0, width, height);
    this.baseCtx.save();
    this.baseCtx.lineWidth = 1;

    const edges = this.data.edges;
    const maxEdges = 2000;
    const step = edges.length > maxEdges ? Math.ceil(edges.length / maxEdges) : 1;

    const edgeStroke =
      getComputedStyle(document.body).getPropertyValue("--edge-stroke").trim() ||
      "rgba(74, 199, 255, 0.12)";
    this.baseCtx.strokeStyle = edgeStroke;
    for (let i = 0; i < edges.length; i += step) {
      const edge = edges[i];
      if (edge.deleted) {
        continue;
      }
      const from = this.positions[edge.src.which];
      const to = this.positions[edge.dest.which];
      if (!from || !to) {
        continue;
      }
      this.baseCtx.beginPath();
      this.baseCtx.moveTo(from.x, from.y);
      this.baseCtx.lineTo(to.x, to.y);
      this.baseCtx.stroke();
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
    if (!this.data || this.currentIndex < 0) {
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
          this.overlayCtx.strokeStyle = `rgba(${jumpRgb}, ${alpha})`;
          this.overlayCtx.lineWidth = 2;
          this.overlayCtx.beginPath();
          this.overlayCtx.moveTo(from.x, from.y);
          this.overlayCtx.lineTo(to.x, to.y);
          this.overlayCtx.stroke();
        }
      } else {
        this.jumpLine = null;
      }
    }
  }

  private handleClick(event: MouseEvent) {
    if (!this.data || !this.onSelect || this.positions.length === 0) {
      return;
    }
    const rect = this.overlayCanvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    const dx = x - cx;
    const dy = y - cy;
    const distance = Math.sqrt(dx * dx + dy * dy);
    const ringTolerance = Math.max(30, this.ringRadius * 0.12);
    if (distance < this.ringRadius - ringTolerance || distance > this.ringRadius + ringTolerance) {
      return;
    }
    const angle = Math.atan2(dy, dx) + Math.PI / 2;
    const normalized = (angle < 0 ? angle + Math.PI * 2 : angle) / (Math.PI * 2);
    const index = Math.floor(normalized * this.data.beats.length);
    const clamped = Math.max(0, Math.min(this.data.beats.length - 1, index));
    this.onSelect(clamped);
  }
}
