export function attachVisualizationResize(
  visualizations: Array<{ resizeNow: () => void }>,
  panel: HTMLElement
) {
  const handleResize = () => {
    visualizations.forEach((viz) => viz.resizeNow());
  };
  const hasResizeObserver =
    typeof (globalThis as { ResizeObserver?: unknown }).ResizeObserver !==
    "undefined";
  if (hasResizeObserver) {
    const observer = new ResizeObserver(() => {
      handleResize();
    });
    observer.observe(panel);
  } else {
    window.addEventListener("resize", handleResize);
  }
}
