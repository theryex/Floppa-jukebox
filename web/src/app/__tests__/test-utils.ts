export function setWindowUrl(url: string) {
  const nextUrl = new URL(url);
  const existing = (globalThis.window ?? {}) as Record<string, unknown>;
  globalThis.window = {
    ...existing,
    location: nextUrl,
    history: {
      replaceState: (_: unknown, __: unknown, next: string) => {
        (globalThis.window as { location: URL }).location = new URL(next);
      },
      pushState: (_: unknown, __: unknown, next: string) => {
        (globalThis.window as { location: URL }).location = new URL(next);
      },
    },
  } as unknown as Window;
}

export function setNow(nowMs: number) {
  const original = Date.now;
  Date.now = () => nowMs;
  return () => {
    Date.now = original;
  };
}
