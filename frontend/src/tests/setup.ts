import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock Web Audio API classes since jsdom doesn't support them out of the box
class MockAudioContext {
  state = 'suspended';
  audioWorklet = {
    addModule: vi.fn().mockResolvedValue(undefined),
  };
  createMediaStreamSource() {
    return {
      connect: vi.fn(),
    };
  }
  close() {
    return Promise.resolve();
  }
  destination = {};
}

class MockAudioWorkletNode {
  port = {
    onmessage: null,
  };
  connect() {}
  disconnect() {}
}

(window as any).AudioContext = MockAudioContext;
(window as any).webkitAudioContext = MockAudioContext;
(window as any).AudioWorkletNode = MockAudioWorkletNode;

// Mock MediaDevices
Object.defineProperty(window.navigator, 'mediaDevices', {
  value: {
    getUserMedia: vi.fn(),
  },
  writable: true,
});
