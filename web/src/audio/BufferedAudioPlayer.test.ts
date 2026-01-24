import { beforeEach, describe, expect, it, vi } from "vitest";
import { BufferedAudioPlayer } from "./BufferedAudioPlayer";

class MockGainNode {
  gain = { value: 1 };
  connect = vi.fn();
}

class MockSourceNode {
  buffer: AudioBuffer | null = null;
  onended: (() => void) | null = null;
  connect = vi.fn();
  disconnect = vi.fn();
  start = vi.fn();
  stop = vi.fn();
}

class MockAudioContext {
  currentTime = 0;
  destination = {};
  createGain() {
    return new MockGainNode();
  }
  createBufferSource() {
    return new MockSourceNode();
  }
  decodeAudioData(buffer: ArrayBuffer) {
    const audioBuffer = { duration: buffer.byteLength } as AudioBuffer;
    return Promise.resolve(audioBuffer);
  }
  resume = vi.fn();
  state: AudioContextState = "running";
}

describe("BufferedAudioPlayer", () => {
  beforeEach(() => {
    (globalThis as any).AudioContext = MockAudioContext;
  });

  it("clamps and returns volume", () => {
    const player = new BufferedAudioPlayer();
    player.setVolume(2);
    expect(player.getVolume()).toBe(1);
    player.setVolume(-1);
    expect(player.getVolume()).toBe(0);
  });

  it("plays and pauses when a buffer is loaded", async () => {
    const player = new BufferedAudioPlayer();
    await player.loadBuffer({ duration: 5 } as AudioBuffer);
    player.play();
    expect(player.isPlaying()).toBe(true);
    player.pause();
    expect(player.isPlaying()).toBe(false);
  });

  it("seeks while playing", async () => {
    const player = new BufferedAudioPlayer();
    await player.loadBuffer({ duration: 10 } as AudioBuffer);
    player.play();
    player.seek(5);
    expect(player.isPlaying()).toBe(true);
    expect(player.getCurrentTime()).toBeGreaterThanOrEqual(0);
  });

  it("decode loads buffer", async () => {
    const player = new BufferedAudioPlayer();
    await player.decode(new ArrayBuffer(3));
    expect(player.getDuration()).toBe(3);
  });
});
