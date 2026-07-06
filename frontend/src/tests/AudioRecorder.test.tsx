import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { AudioRecorder } from '../components/AudioRecorder';

describe('AudioRecorder Component Tests', () => {
  let mockStream: any;
  let mockWs: any;

  beforeEach(() => {
    vi.useFakeTimers();

    // Reset mocks
    mockStream = {
      getTracks: vi.fn().mockReturnValue([{ stop: vi.fn() }]),
    };
    (navigator.mediaDevices.getUserMedia as any).mockResolvedValue(mockStream);

    // Mock WebSocket globally
    mockWs = {
      readyState: 0, // CONNECTING
      send: vi.fn(),
      close: vi.fn(),
      onopen: null,
      onmessage: null,
      onerror: null,
      onclose: null,
    };

    // Override WebSocket constructor globally
    (window as any).WebSocket = vi.fn().mockImplementation(function() {
      mockWs.readyState = 1; // OPEN
      setTimeout(() => {
        if (mockWs.onopen) mockWs.onopen();
      }, 0);
      return mockWs;
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('renders start button initially', () => {
    render(<AudioRecorder onTranscriptChange={() => {}} onStatusChange={() => {}} />);
    expect(screen.getByText(/Start Recording/i)).toBeInTheDocument();
  });

  it('transitions to recording state when clicked', async () => {
    const onStatusChange = vi.fn();
    render(<AudioRecorder onTranscriptChange={() => {}} onStatusChange={onStatusChange} />);

    const startBtn = screen.getByText(/Start Recording/i);
    await act(async () => {
      fireEvent.click(startBtn);
    });

    // Verify microphone access was requested
    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled();

    // Verify status transition and stop button is visible
    expect(onStatusChange).toHaveBeenCalledWith('recording');
    expect(screen.getByText(/Stop Recording/i)).toBeInTheDocument();
  });

  it('displays error alert on microphone permission denial', async () => {
    const onStatusChange = vi.fn();
    // Simulate permission denial
    const error = new Error('Permission denied');
    error.name = 'NotAllowedError';
    (navigator.mediaDevices.getUserMedia as any).mockRejectedValue(error);

    render(<AudioRecorder onTranscriptChange={() => {}} onStatusChange={onStatusChange} />);

    const startBtn = screen.getByText(/Start Recording/i);
    await act(async () => {
      fireEvent.click(startBtn);
    });

    // Alert should be displayed on mic denial
    expect(screen.getByText(/Microphone permission was denied/i)).toBeInTheDocument();
    expect(onStatusChange).toHaveBeenCalledWith('error');
  });

  it('resets state and triggers error on WebSocket disconnection during recording', async () => {
    const onStatusChange = vi.fn();
    render(<AudioRecorder onTranscriptChange={() => {}} onStatusChange={onStatusChange} />);

    // Start recording
    const startBtn = screen.getByText(/Start Recording/i);
    await act(async () => {
      fireEvent.click(startBtn);
    });

    // Trigger premature WS close
    await act(async () => {
      if (mockWs.onclose) {
        mockWs.onclose({ code: 1006 } as any);
      }
    });

    // Verify error transition is triggered
    expect(onStatusChange).toHaveBeenLastCalledWith('error');
    expect(screen.getByText(/WebSocket connection closed unexpectedly/i)).toBeInTheDocument();
    expect(screen.getByText(/Start Recording/i)).toBeInTheDocument();
  });
});
