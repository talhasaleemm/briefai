import React, { useState, useRef, useEffect } from 'react';
import { getAccessToken } from '../api/client';

interface AudioRecorderProps {
  onTranscriptChange: (text: string) => void;
  onStatusChange: (status: 'idle' | 'recording' | 'error') => void;
  onFinalSegments?: (segments: any[]) => void;
  onRecordingFinished?: () => void;
}

export const AudioRecorder: React.FC<AudioRecorderProps> = ({
  onTranscriptChange,
  onStatusChange,
  onFinalSegments,
  onRecordingFinished,
}) => {
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isAnalyserSupported, setIsAnalyserSupported] = useState<boolean>(true);
  
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const webSocketRef = useRef<WebSocket | null>(null);
  const transcriptBufferRef = useRef<string>('');
  const isRecordingRef = useRef<boolean>(false);
  const isWsAuthenticatedRef = useRef<boolean>(false);

  // Web Audio Analyser references
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafIdRef = useRef<number | null>(null);
  const barsRef = useRef<(SVGRectElement | null)[]>([]);
  const numBars = 12;

  // Clean up on unmount
  useEffect(() => {
    return () => {
      stopRecording();
    };
  }, []);

  const updateWaveform = () => {
    if (!isRecordingRef.current || !analyserRef.current) {
      return;
    }

    const analyser = analyserRef.current;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyser.getByteFrequencyData(dataArray);

    // Map frequency data to the SVG bar heights
    for (let i = 0; i < numBars; i++) {
      // Sample from the frequency spectrum (low to mid range is best for speech)
      const dataIdx = Math.floor((i / numBars) * (bufferLength * 0.6));
      const val = dataArray[dataIdx] || 0;
      
      // Calculate height between 4px and 34px (base height 2px, max dynamic 32px)
      const height = 4 + (val / 255) * 30;
      const y = 20 - height / 2; // vertically centered in 40px viewBox
      
      const bar = barsRef.current[i];
      if (bar) {
        bar.setAttribute('height', height.toString());
        bar.setAttribute('y', y.toString());
      }
    }

    rafIdRef.current = requestAnimationFrame(updateWaveform);
  };

  const startRecording = async () => {
    if (isRecordingRef.current || webSocketRef.current) {
      return;
    }

    setErrorMessage(null);
    transcriptBufferRef.current = '';
    onTranscriptChange('');
    setIsAnalyserSupported(true);

    try {
      // 1. Request microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      mediaStreamRef.current = stream;

      // 2. Initialize AudioContext and AudioWorklet
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      audioContextRef.current = audioContext;

      try {
        await audioContext.audioWorklet.addModule('/audio-processor.js');
      } catch (workletErr: any) {
        console.error('AudioWorklet load failed:', workletErr);
        throw new Error(`AudioWorklet failed to load: ${workletErr.message || workletErr}`);
      }

      const sourceNode = audioContext.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(audioContext, 'audio-processor');
      workletNodeRef.current = workletNode;

      // 3. Set up Web Audio Analyser (Visualizer) with graceful fallback
      try {
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 64; // Small fft for simple visual bars
        sourceNode.connect(analyser);
        analyserRef.current = analyser;
      } catch (analyserErr) {
        console.warn(
          'Web Audio AnalyserNode initialization failed. Falling back to CSS wave animation.',
          analyserErr
        );
        setIsAnalyserSupported(false);
      }

      // 4. Open WebSocket only AFTER AudioWorklet is ready
      isWsAuthenticatedRef.current = false;
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/transcription/stream`;
      console.log('Opening WebSocket:', wsUrl);
      const ws = new WebSocket(wsUrl);
      webSocketRef.current = ws;

      ws.onopen = () => {
        console.log('Transcription WebSocket connected, sending auth token');
        const token = getAccessToken();
        ws.send(JSON.stringify({ action: 'auth', token }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('WS message received:', data);

          if (data.type === 'info' && data.message && data.message.includes('Welcome')) {
            console.log('Handshake successful, initializing config');
            isWsAuthenticatedRef.current = true;
            ws.send(JSON.stringify({ action: 'config', sample_rate: 16000, language: 'en' }));
          } else if (data.type === 'segment' && data.text) {
            transcriptBufferRef.current = (transcriptBufferRef.current + ' ' + data.text).trim();
            onTranscriptChange(transcriptBufferRef.current);
          } else if (data.type === 'final' && data.transcript) {
            transcriptBufferRef.current = data.transcript;
            onTranscriptChange(data.transcript);
            if (onFinalSegments && data.segments) {
              onFinalSegments(data.segments);
            }
            if (onRecordingFinished) {
              onRecordingFinished();
            }
          } else if (data.type === 'error') {
            console.error('Backend transcription error:', data.message);
          }
        } catch (err) {
          console.error('Error parsing WS message:', err, event.data);
        }
      };

      ws.onerror = (err) => {
        console.error('WebSocket Error:', err);
        handleFailure('WebSocket error occurred mid-stream.');
      };

      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        if (isRecordingRef.current) {
          handleFailure(`WebSocket closed unexpectedly (code ${event.code}).`);
        }
      };

      // 5. Send audio chunks from worklet to WebSocket
      workletNode.port.onmessage = (event) => {
        const float32Data: Float32Array = event.data;
        if (ws.readyState === WebSocket.OPEN && isWsAuthenticatedRef.current) {
          ws.send(float32Data.buffer as ArrayBuffer);
        }
      };

      // 6. Connect audio graph
      sourceNode.connect(workletNode);
      workletNode.connect(audioContext.destination);

      isRecordingRef.current = true;
      setIsRecording(true);
      onStatusChange('recording');

      // 7. Start visualizer loop if analyser is active
      if (analyserRef.current) {
        rafIdRef.current = requestAnimationFrame(updateWaveform);
      }

    } catch (err: any) {
      console.error('Recording initialization failed:', err);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        handleFailure('Microphone permission was denied. Please allow microphone access in your browser settings.');
      } else {
        handleFailure(`Failed to initialize recorder: ${err.message || err}`);
      }
    }
  };

  const stopRecording = () => {
    isRecordingRef.current = false;
    setIsRecording(false);
    onStatusChange('idle');

    if (rafIdRef.current) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }

    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close().catch(console.error);
      audioContextRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    analyserRef.current = null;

    if (webSocketRef.current && webSocketRef.current.readyState === WebSocket.OPEN) {
      try {
        webSocketRef.current.send(JSON.stringify({ action: 'stop' }));
        console.log('Sent stop signal to backend, waiting for final transcript...');
        setTimeout(() => {
          if (webSocketRef.current) {
            webSocketRef.current.close();
            webSocketRef.current = null;
          }
        }, 10000);
      } catch (err) {
        console.error('Failed to send stop signal:', err);
        webSocketRef.current.close();
        webSocketRef.current = null;
      }
    } else {
      webSocketRef.current = null;
    }
  };

  const handleFailure = (msg: string) => {
    isRecordingRef.current = false;
    setErrorMessage(msg);
    onStatusChange('error');
    setIsRecording(false);
    
    if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
    if (workletNodeRef.current) workletNodeRef.current.disconnect();
    if (audioContextRef.current) audioContextRef.current.close().catch(console.error);
    if (mediaStreamRef.current) mediaStreamRef.current.getTracks().forEach(track => track.stop());
    if (webSocketRef.current) webSocketRef.current.close();

    rafIdRef.current = null;
    workletNodeRef.current = null;
    audioContextRef.current = null;
    mediaStreamRef.current = null;
    webSocketRef.current = null;
    analyserRef.current = null;
  };

  return (
    <div className="audio-recorder-container">
      {errorMessage && (
        <div className="alert alert-error backdrop-blur">
          <div className="alert-content">
            <span className="alert-icon">⚠️</span>
            <p className="alert-text">{errorMessage}</p>
          </div>
          <button className="alert-close-btn" onClick={() => setErrorMessage(null)}>✕</button>
        </div>
      )}

      <div className="recorder-controls">
        {!isRecording ? (
          <button 
            type="button"
            className="btn btn-primary btn-record"
            onClick={startRecording}
          >
            <span className="record-dot pulse"></span>
            Start Recording <kbd className="shortcut-badge ml-2">⌥R</kbd>
          </button>
        ) : (
          <button 
            type="button"
            className="btn btn-danger btn-stop"
            onClick={stopRecording}
          >
            <span className="stop-square"></span>
            Stop Recording <kbd className="shortcut-badge ml-2">⌥R</kbd>
          </button>
        )}
        
        {isRecording && (
          <div className="recording-status">
            {/* Visual Waveform Panel */}
            <div className="visualizer-panel">
              <svg className="live-wave-svg" viewBox="0 0 100 40">
                <defs>
                  <linearGradient id="wave-grad" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor="hsl(var(--primary))" />
                    <stop offset="100%" stopColor="hsl(var(--secondary))" />
                  </linearGradient>
                </defs>
                {Array.from({ length: numBars }).map((_, idx) => {
                  const spacing = 100 / numBars;
                  const x = idx * spacing + spacing / 2 - 2;
                  return (
                    <rect
                      key={idx}
                      ref={(el) => {
                        barsRef.current[idx] = el;
                      }}
                      className={`wave-bar ${!isAnalyserSupported ? 'css-pulse' : ''}`}
                      style={
                        !isAnalyserSupported
                          ? { animationDelay: `${idx * 0.08}s` }
                          : undefined
                      }
                      x={x}
                      y={18}
                      width={4}
                      height={4}
                      rx={2}
                      fill="url(#wave-grad)"
                    />
                  );
                })}
              </svg>
            </div>
            <span className="recording-text">Streaming live audio (16kHz PCM)...</span>
          </div>
        )}
      </div>
    </div>
  );
};
